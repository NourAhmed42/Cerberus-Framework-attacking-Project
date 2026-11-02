# Real result

**Real public test sites and a real local lab · actual captured output · latest update (UTC): {{updated_at}}**

> This document shows what the Cerberus tool integrations actually returned against public practice sites and a separately labelled disposable local lab. The outputs are point-in-time observations, not guaranteed future results. No simulated result is presented as real.

<!-- tool:nmap -->
<!-- tool:sqlmap -->
<!-- tool:metasploit -->

## At a glance

{{summary_table}}

**Why not `127.0.0.1`?** The earlier beginner lab starts a temporary intentionally vulnerable service there, so it does have something to test during the command. The Nmap and sqlmap results below use actual public websites; the separate Metasploit result is explicitly local.

**Read results carefully.** Open ports and service versions can change; a HIGH result is a finding for a deliberately vulnerable training site, not for your application. A negative, failure, or timeout is not proof that a site is secure. Each entry below states its last attempt and any previous successful capture.

## Authorization and limits

- **Nmap:** `scanme.nmap.org`. Its operator explicitly permits Nmap scans, but not exploits or denial of service, and asks for no more than 12 scans per day. This report uses one narrow TCP scan of ports 22, 80, and 443, with light service detection and **no NSE scripts**.
- **sqlmap:** `https://sekumart.sekuripy.hr/product.php?id=1`. SekuriPy operates this public, intentionally vulnerable sqlmap playground. This report tests only the `id` parameter of this page using GET, level 1, risk 1, one thread and error-based detection. No dump, file access, OS command, or database enumeration is requested.
- Check the current site policies before each refresh. Permission for one demo does not authorize testing another website. Do not repeatedly run public scans or set up automatic polling.

<div class="page-break"></div>

# 1. Nmap — real public scan

{{nmap_status}}

### Cerberus framework output

This is a readable selection of fields from the actual `nmap_scanner` finding, not a simulated terminal transcript.

{{nmap_framework}}

### Nmap's actual XML output — excerpt

The adapter requests XML (`-oX -`). The following elements and attributes come from that run; they are reformatted and other XML is omitted. Closed or filtered ports do not appear as open findings.

{{nmap_raw}}

**How to read it:** `open` means that a connection was accepted during this scan. `service`, `product`, and `version` are Nmap's observations or guesses; they are not, by themselves, proof of a vulnerability. Empty output, a skipped module, or an error is not a successful scan.

<div class="page-break"></div>

# 2. sqlmap — real public scan

{{sqlmap_status}}

### Cerberus framework output

This is a readable selection of fields from the actual `sqlmap_scanner` finding produced by the framework. `verified: false` means a separate human validation has not been recorded.

{{sqlmap_framework}}

### How to read the finding

- **HIGH / CWE-89** means sqlmap reported a possible SQL injection in the specified training-site parameter. Review and independently validate it.
- The recorded method, parameter, detection technique, and DBMS help identify the affected request.
- The adapter deliberately omits raw payloads from the framework finding and does not request a database dump. A separate excerpt of the real sqlmap console output appears on the next page.

<div class="page-break"></div>

# 3. sqlmap — actual console excerpt

The following is a selected excerpt from the real sqlmap subprocess output. It can include the detection payload sqlmap generated for the public practice site. Lines may be omitted; the excerpt is not fabricated. Never replay probes on an unauthorized site.

{{sqlmap_raw}}

**Important:** Payloads, timing, warnings, DBMS details, and the number of requests may change each time. The normal integration stores normalized evidence rather than the entire console transcript. No customer credentials or application secrets were used in this public example.

<div class="page-break"></div>

# 4. Metasploit — genuine local integration check

{{metasploit_status}}

No public Metasploit scan was performed. In particular, `scanme.nmap.org` authorizes Nmap, not a Metasploit scan. The public status therefore remains **NOT TESTED**.

### Genuine Cerberus result on a temporary local listener

The repaired adapter authenticated to a genuine Metasploit 6.5.9 `msfrpcd` and ran the reviewed `auxiliary/scanner/portscan/tcp` module against disposable IPv4 and IPv6 loopback listeners. The Cerberus execution engine and scanner produced the following real findings. They are **local integration results**, not Internet-site results. The IPv6 check exposed and verified a parser fix: an open IPv6 port had previously been incorrectly reported as absent. Unrecognized open-port output is now treated as incomplete, not as a clean result.

{{metasploit_local}}

The earlier standalone check and failed old adapter are preserved in the data as a dated historical result. The later local integration pass does not establish that arbitrary modules or public targets are safe.

### Important framework boundaries

The API, AI agent, and interface remain disconnected from these modules. Structured scope/default-port checks, Metasploit option boundaries, and Nmap script restrictions were added; testing windows are refused rather than enforced. Ordinary hostname DNS is not pinned, the legal testing period is not automatically loaded, and background jobs/dependency advisories still require work. The framework is **not production-ready**.

<div class="page-break"></div>

# 5. All three genuine tools — one local scheduler plan

This separate check used **real Nmap, real sqlmap, and a real `msfrpcd`**, in that order, through the Cerberus engine and scheduler. The intentionally vulnerable HTTP target and a second closed TCP port were created only on `127.0.0.1`; both ports were explicitly approved. The temporary services have since stopped. This is not a public-site or Mac/Windows result.

{{three_real_tools_local}}

Nmap saved its open-port result in the engagement's shared state, and sqlmap recorded its detection there. **Metasploit did not automatically consume Nmap's result:** it scanned both scope-approved ports, including the closed one. Sequential execution is working; automatic result handoff is not implemented. The three out-of-scope requests checked in this lab were refused before execution; this limited check is not a security certification.

### First-start timeout

In an earlier isolated check, the first genuine console creation exceeded the old 10-second RPC timeout. The scanner reported an incomplete result, and one unclaimed console remained on that disposable daemon; the lab operator explicitly removed it. The default and example now use **60 seconds per RPC request**. In a later fresh-profile check, the first console took about 15 seconds and the plan passed with the new default. In the latest genuine run, the daemon was started moments before the check, and its first console took 17.8 seconds. A 60-second limit is still finite and cannot guarantee every startup will succeed; a timed-out console creation may still leave an untracked console on the daemon. Use a dedicated daemon for testing and do not remove other users' consoles.

An existing private `.env` value overrides the new default. If it already sets `MSF_RPC_TIMEOUT=10`, review it and change it to `60` before using a real daemon. This does not affect the beginner simulator, and this work did not edit any private `.env` file.

<div class="page-break"></div>

# 6. Refreshing and maintaining this PDF

### What updates automatically

The on-demand refresh command reruns the selected **real**, fixed public-site checks, saves their latest results in `docs/real_results.json`, and rebuilds `docs/real result.pdf`. It does not run in the background or automatically scan sites when code changes. A failure is labelled as a failure; an older successful capture, if available, is separately dated. The local Nmap limit is best-effort: it cannot coordinate concurrent runners or count scans from other devices. You must follow the operator's global daily limit yourself.

First install the backend developer requirements, Nmap and sqlmap as described in the beginner guide. Review the operators' current policies, then run from the project root:

**Mac / zsh**
```zsh
./backend/.venv/bin/python scripts/live_tests/public_tool_results.py all --confirm-public-tests
```
**Windows / PowerShell**
```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\public_tool_results.py all --confirm-public-tests
```

Use `nmap` or `sqlmap` instead of `all` to refresh just one. `all` means the two supported real checks, sequentially on **different public sites**; it does not include real Metasploit. Set `SQLMAP_PATH` or `NMAP_PATH` first if the binary is not on PATH. The command asks for explicit confirmation via the flag and accepts no arbitrary target.

### Every time a tool is added

The contributor must add it to this document and the results data, find and verify an authorized test site and specific scope, perform a safe real test if feasible, record the genuine timestamped output, and rebuild and review this PDF. If no real test is possible, label the tool **not tested** and say why. The repository tests flag a missing registered-tool entry or a PDF whose source/data have changed; they cannot perform or certify a public scan.

### References and permissions

- Nmap's permitted scope and rate limit: [nmap.org/book/man-examples.html](https://nmap.org/book/man-examples.html)
- SekuMart's operator and public practice scope: [sekuripy.hr/labs/sekumart](https://www.sekuripy.hr/labs/sekumart/)
- sqlmap's official playground reference: [sqlmap FAQ](https://github.com/sqlmapproject/sqlmap/wiki/FAQ)
- Metasploit's real RPC protocol: [Rapid7 RPC API](https://docs.rapid7.com/metasploit/rpc-api/)

The captures were made from a Linux sandbox; Mac and Windows refresh commands have not been executed on those operating systems for this edition. The displayed results are not a production assessment.
