import argparse
from openai import OpenAI
import random
from tqdm import tqdm
import json
import os
import re
from src.utils import load_jsonlines
import datasets

import numpy as np
import torch
import time
import os
import vllm
from src.open_scholar import OpenScholar


from FlagEmbedding import FlagReranker


def remove_citations(sent):
    return re.sub(r"\[\d+", "", re.sub(r" \[\d+", "", sent)).replace(" |", "").replace("]", "")

def load_hf_tokenizer(
        model_name_or_path,
        tokenizer_name_or_path=None,
        use_fast_tokenizer=True,
        padding_side="left",
        token=os.getenv("HF_TOKEN", None),
    ):
        from transformers import AutoTokenizer

        # Need to explicitly import the olmo tokenizer.
        if not tokenizer_name_or_path:
            tokenizer_name_or_path = model_name_or_path
        try:
            tokenizer = AutoTokenizer.from_pretrained(tokenizer_name_or_path, use_fast=use_fast_tokenizer, token=token)
        except:
            # some tokenizers (e.g., GPTNeoXTokenizer) don't have the slow or fast version, so we just roll back to the default one
            tokenizer = AutoTokenizer.from_pretrained(tokenizer_name_or_path, token=token)
        # set padding side to left for batch generation
        tokenizer.padding_side = padding_side
        # set pad token to eos token if pad token is not set (as is the case for llama models)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            tokenizer.pad_token_id = tokenizer.eos_token_id
        return tokenizer

def process_paragraph(text):
    text = text.replace("<cit.>", "")
    text = remove_citations(text)
    return text

def process_input_data(data, use_contexts=True):
    processed_data = []
    for item in data:
        if "answer" not in item:
            item["answer"] = ""
        if "input" not in item:
            if "question" in item:
                item["input"] = item["question"]
            if "query" in item:
                item["input"] = item["query"]

        new_ctxs = []
        if use_contexts is True:
            # normalize ctx format for different retrieval APIs
            for ctx in item["ctxs"]:
                if type(ctx) is list:
                    for c in ctx:
                        if type(c) is dict:
                            new_ctxs.append(c)
                if type(ctx) is dict:
                    new_ctxs.append(ctx)
            item["ctxs"] = new_ctxs

            # remove duplicated contexts
            processed_paras = []
            for ctx in tqdm(item["ctxs"]):
                if "retrieval text" in ctx:
                    ctx["text"] = ctx["retrieval text"]
                if ctx["text"] is None or len(ctx["text"]) ==0:
                    continue
                if type(ctx["text"]) != str:
                    ctx["text"] = " ".join(ctx["text"]["contexts"])
                ctx["text"] = process_paragraph(ctx["text"])
                if "title" not in ctx:
                    ctx["title"] = ""
                processed_paras.append(ctx)

            processed_paras_dicts = {paper["text"][:100] + paper["title"]: paper for paper in processed_paras}
            processed_paras = list(processed_paras_dicts.values())

            item["ctxs"] = processed_paras
            item["original_ctxs"] = processed_paras
        processed_data.append(item)
    return processed_data
        
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", type=str, help="path to input file")
    parser.add_argument("--output_file", type=str, help="path to output file")
    parser.add_argument("--task_name", type=str, default="default", help="default indicates multi paper QA tasks. If you want to test models on SciFact, PubmedQA or QASA, change the task names accordingly.")
    parser.add_argument("--dataset", type=str, default=None, help="specify the HF data path if you load them from HF datasets.")

    # Model loading config
    parser.add_argument("--use_contexts", action="store_true", help="set True whenever you use RAG pipelines.")
    parser.add_argument("--model_name", type=str, help="model name")
    parser.add_argument("--api", type=str, help="specify the API provider if you use together or anyscale to run Llama models.")
    parser.add_argument("--api_key_fp", type=str, help="specify the path to the text file containing API key.")
    parser.add_argument("--download_dir", type=str, default="./cache", help="specify the model download dir.")
    parser.add_argument("--use_slow_tokenizer", action="store_true")
    parser.add_argument("--llama3", action="store_true", help="use llama3 chat template")    
    
    # Inference config (generation)
    parser.add_argument("--top_n", type=int, default=10, help="the number of the passages used during generation at each step.")
    parser.add_argument("--feedback", action="store_true")
    parser.add_argument("--posthoc_at", action="store_true")
    parser.add_argument("--max_tokens", type=int, default=3000)
    parser.add_argument("--zero_shot", action="store_true", help="zero shot inference")

    # Inference config (reranking)
    parser.add_argument("--ranking_ce", action="store_true", help="model rearnking")
    parser.add_argument("--reranker", type=str, help="model rearnking")   
    parser.add_argument("--min_citation", type=int, default=None, help="minimum citations")   
    parser.add_argument("--norm_cite", action="store_true", help="add normalized citation for predictions.")   
    parser.add_argument("--ss_retriever", action="store_true", help="add normalized citation for predictions.")  
    parser.add_argument("--use_abstract", action="store_true", help="use abstract during reranking") 
    parser.add_argument("--max_per_paper", type=int, default=None, help="maximum number of passages per paper.") 
    
    # For debugging purposes
    parser.add_argument("--skip_generation", action="store_true")
    parser.add_argument("--sample_k", type=int, default=-1)
    parser.add_argument("--reverse", action="store_true", help="reverse data iteration order")
    parser.add_argument("--start_index", type=int, default=None, help="starting point")

    args = parser.parse_args()

    # load input data
    if args.input_file is not None:
        if args.input_file.endswith("jsonl"):
            data = load_jsonlines(args.input_file)
        else:
            data = json.load(open(args.input_file))
            if "data" in data:
                data = data["data"]
    elif args.dataset is not None:
        data = list(datasets.load_dataset(args.dataset)["test"])
    else:
        raise ValueError("Please provide either input_file or dataset")
    
    # Randomly sample the data if sample_k is specified
    if args.sample_k > -1:
        data = random.sample(data, k=args.sample_k)
        data = data[:args.sample_k]
        
    if args.start_index is not None:
        data = data[args.start_index:]
        
    final_results = []
    
    # Restarting from existing results if there's file whose name matches the output file
    if os.path.isfile(args.output_file):
        final_results = json.load(open(args.output_file))["data"]
        data = data[len(final_results):]
        
        print("restarting from {}".format(len(final_results)))


    # Set up API models if you are using API models
    if args.api is not None:
        if args.api == "together":
            base_url = "https://api.together.xyz"
        elif args.api =="anyscale":
            base_url = "https://api.endpoints.anyscale.com/v1"
        else:
            base_url = None
        with open(args.api_key_fp) as f:
            api_key = f.read()[:-1]
                
        client = OpenAI(
            base_url = base_url,
            api_key = api_key
        )
        api_model_name = args.model_name
        model = None
        tokenizer = None

    # Set up local models 
    else:
        model = vllm.LLM(
            model=args.model_name,
            tokenizer=args.model_name,
            tokenizer_mode="auto",
            tensor_parallel_size=torch.cuda.device_count(),
            download_dir=args.download_dir,
            enforce_eager=True,
            disable_custom_all_reduce=True
        )
        # To apply chat formatting
        tokenizer = load_hf_tokenizer(
            model_name_or_path=args.model_name,
            tokenizer_name_or_path=args.model_name,
            use_fast_tokenizer=not args.use_slow_tokenizer,
        )
        client = None
        api_model_name = None
        
    # load reranker model if it is passed
    if args.reranker is not None:
        reranker = FlagReranker(args.reranker, use_fp16=True)
    else:
        reranker = None
        
    # initialize the agent
    open_scholar = OpenScholar(model=model, tokenizer=tokenizer, \
                        client=client, api_model_name=api_model_name, \
                        use_contexts=args.use_contexts, top_n=args.top_n, \
                        reranker=reranker, min_citation=args.min_citation, \
                        norm_cite=args.norm_cite, ss_retriever=args.ss_retriever)
    
    # process input data
    data = process_input_data(data)

    for item in data:
        if "answer" not in item and "output" in item:
            item["answer"] = item["output"]
    
    # Run OpenScholar inference
    for idx, item in tqdm(enumerate(data)):
        start = time.time()
        updated_item, total_cost = open_scholar.run(item, \
                                ranking_ce=args.ranking_ce, use_feedback=args.feedback, \
                                skip_generation=args.skip_generation, posthoc_at=args.posthoc_at, \
                                llama3_chat="Llama-3" in args.model_name or args.llama3, 
                                task_name=args.task_name, zero_shot=args.zero_shot, \
                                use_abstract=args.use_abstract, max_per_paper=args.max_per_paper,
                                max_tokens=args.max_tokens)
        end = time.time()
        elapsed_time = end - start
        updated_item["total_cost"] = total_cost
        updated_item["elapsed"] = elapsed_time 
        final_results.append(updated_item)

        if idx % 10 == 0:
            with open(args.output_file, "w") as outfile:
                json.dump({"data": final_results}, outfile)

    # Log the output and stats
    print("Total Cost: {} USD".format(np.mean([item["total_cost"] for item in final_results])))
    print("Latency per query: {} sec".format(np.mean([item["elapsed"] for item in final_results])))

    with open(args.output_file, "w") as outfile:
        json.dump({"data": final_results}, outfile)

if __name__ == '__main__':
    main()