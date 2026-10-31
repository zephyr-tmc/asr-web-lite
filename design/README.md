# Summary workspace design reference

Throwaway UI prototype; all transcript text and model results are synthetic.

Question: which reading and source-checking layout supports the summary workflow?
Verdict: user approved the warm paper and jade reader layout on 2026-10-31. Production uses that layout without prototype controls or preset responses.

Run `python -m http.server 8876 --directory design`, then open `http://127.0.0.1:8876/prototype-summary.html?variant=reader`. Other layout variants remain available from the prototype switcher.
