import json
from pathlib import Path
r=json.loads(Path('.howhow/experiments/claimledger-benchmark-001.json').read_text())
obs=r['raw_observations']
invalid = [o for o in obs if o['condition'] == 'mutated'][0]
hash_rate = float(r['metrics']['content_addressed_invalid_acceptance_rate'])
path_rate = float(r['metrics']['path_only_invalid_acceptance_rate'])
Path('paper/tables/results.tex').write_text('''\\begin{tabular}{lrrr}\\toprule
Condition & Hash rejects & Path-only accepts & Hash latency (microseconds)\\\\\\midrule
%s & %s & %s & %.3f\\\\
%s & %s & %s & %.3f\\\\\\bottomrule
\\end{tabular}
''' % (obs[0]['condition'], int(obs[0]['content_addressed_rejects']), int(obs[0]['path_only_accepts']), obs[0]['latency_us'], obs[1]['condition'], int(obs[1]['content_addressed_rejects']), int(obs[1]['path_only_accepts']), obs[1]['latency_us']), encoding='utf-8')
Path('paper/figures/figure.tex').write_text(r'''\\documentclass{standalone}
\\usepackage{tikz}
\\begin{document}
\\begin{tikzpicture}[x=2.5cm,y=2.8cm]
\\draw[->] (0,0) -- (2.8,0) node[right] {condition};
\\draw[->] (0,0) -- (0,1.3) node[above] {invalid acceptance rate};
\\fill[blue!60] (0.35,0) rectangle (0.85,{hash_rate});
\\fill[red!60] (1.35,0) rectangle (1.85,{path_rate});
\\node at (0.6,-0.15) {hash};
\\node at (1.6,-0.15) {path-only};
\\node at (0.6,0.1) {0.0};
\\node at (1.6,1.08) {1.0};
\\end{tikzpicture}
\\end{document}
'''.replace('{hash_rate}', str(hash_rate)).replace('{path_rate}', str(path_rate)).replace(chr(92)+chr(92), chr(92)), encoding='utf-8')
print('generated table and figure source from experiment-success raw observations')
