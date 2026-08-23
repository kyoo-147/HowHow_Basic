# Reproducibility

From this directory:

```powershell
python run_benchmark.py
$env:PYTHONPATH="../.."
python -m howhow experiment record experiment-success.json
python -m howhow paper build --strict
python -m howhow package
```

The benchmark is deterministic in decisions and seed declaration; measured nanosecond timing is machine-dependent. The package has no credentials, private paths, or network-dependent build inputs. The paper's OpenAlex retrieval is preserved as provenance but is not required to compile.
