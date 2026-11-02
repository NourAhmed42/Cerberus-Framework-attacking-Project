# Output only

**Run date: 2 November 2026 (Cairo) · Latest all-tools run: 2026-11-02 15:55 UTC**

This PDF contains only the output: what each tool printed, what the saved results say, and what the local lab and tests printed. It does not repeat how to use the tools; the guides cover that. Each block is labelled with how the result was produced:

- **PUBLIC:** a real public site that the operator allows this tool to test.
- **LOCAL REAL:** the real tool on a temporary target on this computer.
- **SIMULATED:** a fake Metasploit response, used to check the parser. It is not a real Metasploit scan.
- **TESTS:** the automated test suite.

> A captured result is a point-in-time observation. A finding on a practice site is not a finding about any other system.

## 1. All-tools run (concurrent, three engagements)

Command: `run_all_tools.py --confirm-public-tests`. The three engagements started at the same second.

| Engagement | Label | Target | Tool version | Started (UTC) | Finished (UTC) | Status |
|---|---|---|---|---|---|---|
| Nmap | PUBLIC | `http://scanme.nmap.org/` | Nmap 7.95 | 15:55:41 | 15:56:00 | CAPTURED |
| sqlmap | PUBLIC | `https://sekumart.sekuripy.hr/product.php?id=1` (parameter `id` only) | 1.10.11.2#dev | 15:55:41 | 15:55:48 | CAPTURED |
| Metasploit | LOCAL REAL | `127.0.0.1:45201` (temporary listener) | Metasploit 6.5.9 (real `msfrpcd`) | 15:55:41 | 15:55:56 | CAPTURED |

**What each row means:**

- **Nmap** scanned three TCP ports on `scanme.nmap.org` and read the service versions. Nmap is allowed to scan this site only.
- **sqlmap** tested the `id` parameter on one product page and found an error-based SQL injection. It did not extract any data.
- **Metasploit** ran the reviewed port-scan module against a temporary listener on this computer, and reported the open port. No public site allows Metasploit testing.

### 1.1 Nmap output (PUBLIC, `scanme.nmap.org`)

Finding: **Nmap scan: 3 open ports on scanme.nmap.org**

Open ports and services parsed from the Nmap run:

```text
  port 22/TCP  ssh    OpenSSH 6.6.1p1 Ubuntu 2ubuntu2.13
  port 80/TCP  http   Apache httpd 2.4.7
  port 443/TCP  https
```

Nmap raw output (first lines, from the saved run):

```text
<status state="up" reason="user-set" reason_ttl="0" />

<address addr="45.33.32.156" addrtype="ipv4" />

<ports>
  <port protocol="tcp" portid="22">
    <state state="open" reason="syn-ack" reason_ttl="0" />
    <service name="ssh" product="OpenSSH" version="6.6.1p1 Ubuntu 2ubuntu2.13" extrainfo="Ubuntu Linux; protocol 2.0" ostype="Linux" method="probed" conf="10">
      <cpe>cpe:/a:openbsd:openssh:6.6.1p1</cpe>
      <cpe>cpe:/o:linux:linux_kernel</cpe>
    </service>
  </port>
  <port protocol="tcp" portid="80">
    <state state="open" reason="syn-ack" reason_ttl="0" />
    <service name="http" product="Apache httpd" version="2.4.7" extrainfo="(Ubuntu)" method="probed" conf="10">
      <cpe>cpe:/a:apache:http_server:2.4.7</cpe>
```

### 1.2 sqlmap output (PUBLIC, SekuMart `id`)

Finding: **sqlmap reported SQL injection in GET parameter 'id'** (severity: high, CWE: CWE-89)

| Field | Value |
|---|---|
| Parameter | `id` (GET) |
| Technique | error-based |
| Database | MySQL >= 5.1 (MariaDB fork) |
| Component | `/product.php` |

sqlmap raw output (first lines, from the saved run):

```text
sqlmap identified the following injection point(s) with a total of 3 HTTP(s) requests:
---
Parameter: id (GET)
    Type: error-based
    Title: MySQL >= 5.1 AND error-based - WHERE, HAVING, ORDER BY or GROUP BY clause (EXTRACTVALUE)
    Payload: id=1 AND EXTRACTVALUE(2683,CONCAT(0x5c,0x716b6b6b71,(SELECT (ELT(2683=2683,1))),0x7170627871))
---

[15:55:46] [INFO] the back-end DBMS is MySQL
```

### 1.3 Metasploit output (LOCAL REAL, 127.0.0.1)

Finding: **Metasploit auxiliary/scanner/portscan/tcp: 1 open ports on 127.0.0.1**

| Field | Value |
|---|---|
| Module | `auxiliary/scanner/portscan/tcp` |
| Host | `127.0.0.1` |
| Open port | 45201 |
| Options | RHOSTS=127.0.0.1, PORTS=45201, THREADS=10 |

## 2. Each tool on its own (local lab)

Command: `beginner_tools_lab.py <mode>`. Each run starts a temporary target on this computer and stops it at the end.

### 2.1 Nmap alone (LOCAL LAB)

```text
LOCAL LAB: 127.0.0.1:41069 (temporary, intentionally vulnerable)
Metasploit, when selected, is SIMULATED; no real msfrpcd is tested.
MODE: individual nmap integration.
PASS: real Nmap found the local lab's open port 41069.
DONE: temporary local servers stopped; results were not saved to the app database.
```

### 2.2 sqlmap alone (LOCAL LAB)

```text
LOCAL LAB: 127.0.0.1:43779 (temporary, intentionally vulnerable)
Metasploit, when selected, is SIMULATED; no real msfrpcd is tested.
MODE: individual sqlmap integration.
PASS: real sqlmap detected the lab's intentional SQL injection in id.
DONE: temporary local servers stopped; results were not saved to the app database.
```

### 2.3 Metasploit alone (LOCAL LAB, SIMULATED)

```text
LOCAL LAB: 127.0.0.1:35683 (temporary, intentionally vulnerable)
Metasploit, when selected, is SIMULATED; no real msfrpcd is tested.
MODE: individual metasploit integration.
PASS: the Metasploit adapter parsed a SIMULATED response (not msfrpcd).
DONE: temporary local servers stopped; results were not saved to the app database.
```

## 3. The tools together (local lab)

### 3.1 `all`: one plan, one tool after another

```text
LOCAL LAB: 127.0.0.1:46679 (temporary, intentionally vulnerable)
Metasploit, when selected, is SIMULATED; no real msfrpcd is tested.
MODE: one engagement, modules run sequentially: Nmap -> sqlmap -> simulated Metasploit.
PASS: real Nmap found the local lab's open port 46679.
PASS: real sqlmap detected the lab's intentional SQL injection in id.
PASS: the Metasploit adapter parsed a SIMULATED response (not msfrpcd).
DONE: temporary local servers stopped; results were not saved to the app database.
```

### 3.2 `parallel`: three engagements at the same time

```text
LOCAL LAB: 127.0.0.1:40063 (temporary, intentionally vulnerable)
Metasploit, when selected, is SIMULATED; no real msfrpcd is tested.
MODE: three independent engagements run concurrently against the same local lab.
PASS: real Nmap found the local lab's open port 40063.
PASS: real sqlmap detected the lab's intentional SQL injection in id.
PASS: the Metasploit adapter parsed a SIMULATED response (not msfrpcd).
DONE: temporary local servers stopped; results were not saved to the app database.
```

## 4. One-command demo (`run_everything.py`, local steps)

Command: `run_everything.py` (without `--include-public`, so no public site was contacted by the demo).

```text
Step                                    Label                               Status     Time  Note
  Step 1 - Nmap, sqlmap, Metasploit (lab) LOCAL LAB; Metasploit SIMULATED     PASS       3.6s  exit 0
  Step 2 - Automated tests                TESTS                               PASS      16.0s  exit 0
  Step 3 - Public sites + real Metasploit PUBLIC + LOCAL REAL                 SKIP       0.0s  not run; add --include-public to contact scanme.nmap.org and SekuMart

Passed: every step that ran. 1 step(s) were SKIPPED (reasons above).
```

Step 1 is LOCAL LAB with a SIMULATED Metasploit step. Step 2 is the automated test run (TESTS).

## 5. Automated tests

| Run | Result | When |
|---|---|---|
| Tool, framework and beginner-lab tests, no database (`--noconftest`, `-k "not persist"`) | **228 passed**, 2 deselected | 2 Nov 2026, as part of the demo run |
| Full backend suite (temporary PostgreSQL and Redis, removed afterwards) | **385 passed** | 2 Nov 2026, after the last code change |

## 6. Local expansion: more output (nothing new contacted)

These runs use only local targets on this computer. No public site was contacted for this section.

### 6.1 sqlmap lab smoke test (`sqlmap_framework_smoke.py`)

Real sqlmap 1.10.11.2#dev against a local vulnerable lab. The lab also includes a parameterized control, redirects, and a POST form.

```text
PASS: scheduled nmap_scanner, sqlmap_scanner, metasploit_scanner; real sqlmap detected GET SQLi
NOTE: Nmap is real when present; the Metasploit RPC service is a test double.
PASS: parameterized GET control produced no actionable finding
PASS: real sqlmap detected SQLi in an authorized form POST
PASS: selected GET/POST alias parameters left auth and unselected fields unchanged
PASS: out-of-scope HTTP redirects and HTML refreshes were not followed
PASS: two real sqlmap scans ran concurrently in isolated engagements
PASS: real Nmap + real sqlmap + fake Metasploit ran in separate concurrent engagements
PASS: the local lab and temporary sqlmap scan files were cleaned up
```

### 6.2 Framework run (`pentest_framework_smoke.py`)

The framework discovers its 9 modules, runs the web, network and credential modules against a local target, and reports how each external tool is configured.

```text
target: http://127.0.0.1:39405/search?q=cerberus
modules registered: 9
categories: ['auth', 'network', 'tools', 'web']
------------------------------------------------------------
[HIGH    ] SQL Injection (error-based, MySQL) in parameter 'q'
           confidence=high verified=True evidence=2
[INFO    ] Port scan: 1 open of 1 probed
           confidence=certain verified=False evidence=1
[INFO    ] Technology fingerprint: 1 identified
           confidence=high verified=False evidence=1
------------------------------------------------------------
tools registered: 3
  tool: metasploit (status=disconnected, enabled_by_default=False)
  tool: nmap (status=disconnected, enabled_by_default=False)
  tool: sqlmap (status=disconnected, enabled_by_default=False)
module: metasploit_scanner (tools category)
[INFO    ] Metasploit integration disabled
           Metasploit is not enabled for this deployment (MSF_ENABLED=false). Enable it and configure msfrpcd to run Meta...
module: nmap_scanner (tools category)
[INFO    ] Nmap integration disabled
           Nmap is not enabled for this deployment (NMAP_ENABLED=false). Enable it and ensure the nmap binary is installe...
module: sqlmap_scanner (tools category)
[INFO    ] sqlmap integration disabled
           Set SQLMAP_ENABLED=true and install sqlmap to enable this optional scanner....
------------------------------------------------------------
SAFETY GATE OK — out-of-scope refused: Target is not inside the approved engagement scope.
```

**Important:** in the default configuration the three external tools are **disabled** (`NMAP_ENABLED=false`, `SQLMAP_ENABLED=false`, `MSF_ENABLED=false`). The framework reports this honestly. It means the tools only run when they are enabled on purpose. Turning them on in the app is part of the API and AI wiring, which is not done yet.

### 6.3 Automated tests, one line per test (no database)

Command: `pytest --noconftest -v -k "not persist"` on the five tool and framework test files. Total: **228 tests passed, 2 deselected** (the 2 deselected tests need a database).

| Test file | Tests passed |
|---|---|
| `tests/unit/test_pentest_tools.py` | 40 |
| `tests/unit/test_pentest_framework.py` | 42 |
| `tests/unit/test_pentest_safety_regressions.py` | 49 |
| `tests/unit/test_sqlmap_integration.py` | 80 |
| `tests/unit/test_public_tool_results.py` | 17 |

Full list of test names:

```text
# tests/unit/test_pentest_tools.py
  test_tool_registry_discovers_metasploit  PASSED
  test_msf_default_rpc_timeout_allows_slow_first_console  PASSED
  test_adapter_connects_and_reports_version  PASSED
  test_adapter_rejects_bad_password  PASSED
  test_adapter_runs_auxiliary_and_captures_output  PASSED
  test_adapter_refuses_exploit_modules  PASSED
  test_adapter_lists_modules  PASSED
  test_adapter_fail_soft_when_daemon_down  PASSED
  test_module_runs_scan_via_engine  PASSED
  test_msf_port_parser_handles_genuine_ipv4_and_ipv6_shapes[[*] 127.0.0.1:80 - TCP OPEN-127.0.0.1-80]  PASSED
  test_msf_port_parser_handles_genuine_ipv4_and_ipv6_shapes[[+] [::1] - ::1:36305 - TCP OPEN-::1-36305]  PASSED
  test_msf_port_parser_handles_genuine_ipv4_and_ipv6_shapes[[*] [2001:db8::1]:443 - TCP OPEN-2001:db8::1-443]  PASSED
  test_msf_port_parser_handles_genuine_ipv4_and_ipv6_shapes[[*] ::ffff:127.0.0.1:22 - TCP OPEN-::ffff:127.0.0.1-22]  PASSED
  test_msf_unparseable_open_output_is_inconclusive[[*] example.invalid:80 - TCP OPEN]  PASSED
  test_msf_unparseable_open_output_is_inconclusive[[*] 999.999.999.999:80 - TCP OPEN]  PASSED
  test_msf_unparseable_open_output_is_inconclusive[[*] ::1:0 - TCP OPEN]  PASSED
  test_msf_unparseable_open_output_is_inconclusive[[*] ::1:99999 - TCP OPEN]  PASSED
  test_msf_unparseable_open_output_is_inconclusive[[*] fe80::1%eth0:80 - TCP OPEN]  PASSED
  test_msf_ipv6_scan_is_reported_by_framework  PASSED
  test_msf_rejects_unapproved_ipv6_port_even_if_daemon_reports_it  PASSED
  test_module_disabled_yields_info  PASSED
  test_module_refuses_non_auxiliary  PASSED
  test_module_refuses_non_auxiliary_unknown_type  PASSED
  test_module_fail_soft_when_daemon_down  PASSED
  test_unreviewed_exploit_refused_even_with_full_impact  PASSED
  test_future_tools_follow_the_same_contract  PASSED
  test_builtin_module_registry_includes_tool_module  PASSED
  test_tool_registry_discovers_nmap  PASSED
  test_nmap_adapter_connects_and_reports_version  PASSED
  test_nmap_adapter_executes_scan_and_parses_xml  PASSED
  test_nmap_adapter_refuses_intrusive_scripts  PASSED
  test_nmap_adapter_rejects_flag_injection_in_host  PASSED
  test_nmap_adapter_fail_soft_when_binary_missing  PASSED
  test_nmap_module_runs_scan_via_engine  PASSED
  test_nmap_module_disabled_yields_info  PASSED
  test_nmap_module_refuses_intrusive_scripts  PASSED
  test_nmap_module_refuses_destructive_dos_scripts  PASSED
  test_nmap_module_fail_soft_when_binary_unavailable  PASSED
  test_metasploit_and_nmap_run_together_without_conflict  PASSED
  test_nmap_findings_are_shared_but_not_automatically_passed_to_msf  PASSED
# tests/unit/test_pentest_framework.py
  test_registry_discovers_all_builtin_modules  PASSED
  test_registry_categories_and_techniques  PASSED
  test_registry_rejects_duplicate_names  PASSED
  test_registry_discovery_is_isolated_from_broken_modules  PASSED
  test_safety_allows_approved_target  PASSED
  test_safety_refuses_unapproved_target  PASSED
  test_safety_refuses_excluded_target  PASSED
  test_safety_default_scope_allows_nothing  PASSED
  test_safety_enforces_impact_ceiling  PASSED
  test_safety_blocks_destructive_modules  PASSED
  test_safety_enforces_port_policy  PASSED
  test_engine_executes_module_and_normalizes_findings  PASSED
  test_engine_refuses_out_of_scope_execution  PASSED
  test_engine_refuses_roe_impact_violation  PASSED
  test_engine_is_fail_soft_on_module_crash  PASSED
  test_engine_reports_unknown_module  PASSED
  test_engine_bounds_execution_time  PASSED
  test_engine_audit_sink_receives_events  PASSED
  test_evidence_hash_is_deterministic  PASSED
  test_finding_risk_score_and_actionability  PASSED
  test_finding_default_cvss_and_dict_shape  PASSED
  test_scheduler_runs_plan_sequentially_with_progress  PASSED
  test_scheduler_streams_findings_live  PASSED
  test_scheduler_honors_cooperative_cancellation  PASSED
  test_sqli_probe_error_based_detection  PASSED
  test_sqli_probe_boolean_based_detection  PASSED
  test_sqli_probe_clean_target_yields_no_actionable  PASSED
  test_sqli_probe_without_parameters_skips  PASSED
  test_xss_probe_detects_raw_reflection  PASSED
  test_xss_probe_ignores_unrelated_static_tags  PASSED
  test_xss_probe_ignores_payload_already_present_in_baseline  PASSED
  test_xss_failed_request_is_inconclusive[True]  PASSED
  test_xss_failed_request_is_inconclusive[False]  PASSED
  test_xss_probe_encoded_output_is_safe  PASSED
  test_path_traversal_probe_detects_file_read  PASSED
  test_port_scanner_reports_only_scoped_open_ports  PASSED
  test_port_scanner_respects_port_ceiling  PASSED
  test_service_fingerprint_matches_technologies  PASSED
  test_credential_tester_single_attempt_only  PASSED
  test_credential_tester_skips_without_credentials  PASSED
  test_finding_to_vulnerability_dict_mapping  PASSED
  test_context_from_engagement_reads_target_from_context_model  PASSED
# tests/unit/test_pentest_safety_regressions.py
  test_structured_scope_rejects_substrings_and_ambiguous_targets[example.com-https://example.com.attacker.invalid/]  PASSED
  test_structured_scope_rejects_substrings_and_ambiguous_targets[example.com-https://attacker.invalid/?next=example.com]  PASSED
  test_structured_scope_rejects_substrings_and_ambiguous_targets[example.com-https://api.example.com/]  PASSED
  test_structured_scope_rejects_substrings_and_ambiguous_targets[https://example.com-http://example.com/]  PASSED
  test_structured_scope_rejects_substrings_and_ambiguous_targets[https://example.com-https://example.com:444/]  PASSED
  test_structured_scope_rejects_substrings_and_ambiguous_targets[https://example.com/approved-https://example.com/approved-other]  PASSED
  test_structured_scope_rejects_substrings_and_ambiguous_targets[https://example.com/approved-https://example.com/approved/%2e%2e/private]  PASSED
  test_structured_scope_rejects_substrings_and_ambiguous_targets[example.com-https://example.com@attacker.invalid/]  PASSED
  test_explicit_wildcard_only_covers_subdomains_and_url_default_port  PASSED
  test_network_exclusions_and_encoded_paths_fail_closed  PASSED
  test_implicit_and_bare_https_ports_and_windows_are_checked  PASSED
  test_msf_target_port_and_command_overrides_never_reach_daemon[options0]  PASSED
  test_msf_target_port_and_command_overrides_never_reach_daemon[options1]  PASSED
  test_msf_target_port_and_command_overrides_never_reach_daemon[options2]  PASSED
  test_msf_target_port_and_command_overrides_never_reach_daemon[options3]  PASSED
  test_msf_target_port_and_command_overrides_never_reach_daemon[options4]  PASSED
  test_msf_target_port_and_command_overrides_never_reach_daemon[options5]  PASSED
  test_msf_target_port_and_command_overrides_never_reach_daemon[options6]  PASSED
  test_msf_target_port_and_command_overrides_never_reach_daemon[options7]  PASSED
  test_unreviewed_msf_modules_refused_even_under_full_impact[auxiliary/scanner/http/title]  PASSED
  test_unreviewed_msf_modules_refused_even_under_full_impact[exploit/multi/handler]  PASSED
  test_unreviewed_msf_modules_refused_even_under_full_impact[post/test]  PASSED
  test_msf_default_ports_never_fall_back_to_tool_default  PASSED
  test_real_shape_protocol_bytes_delayed_completion_and_logout  PASSED
  test_msf_timeout_is_inconclusive_and_cleans_console  PASSED
  test_msf_console_injection_rejected_before_connect[auxiliary/scanner/portscan/tcp\nrun-options0]  PASSED
  test_msf_console_injection_rejected_before_connect[auxiliary/scanner/portscan/tcp-options1]  PASSED
  test_msf_console_injection_rejected_before_connect[auxiliary/scanner/portscan/tcp-options2]  PASSED
  test_msf_console_injection_rejected_before_connect[auxiliary/scanner/portscan/tcp-options3]  PASSED
  test_msf_refuses_unencrypted_remote_daemon_without_sending_password  PASSED
  test_nmap_wildcards_categories_and_unreviewed_scripts_refused_even_full[*]  PASSED
  test_nmap_wildcards_categories_and_unreviewed_scripts_refused_even_full[safe]  PASSED
  test_nmap_wildcards_categories_and_unreviewed_scripts_refused_even_full[default]  PASSED
  test_nmap_wildcards_categories_and_unreviewed_scripts_refused_even_full[http-*]  PASSED
  test_nmap_wildcards_categories_and_unreviewed_scripts_refused_even_full[http-shellshock]  PASSED
  test_nmap_wildcards_categories_and_unreviewed_scripts_refused_even_full[vuln]  PASSED
  test_only_reviewed_nmap_names_accepted  PASSED
  test_nmap_wildcard_is_rejected_before_binary_invocation  PASSED
  test_path_only_web_approval_cannot_authorize_port_scans  PASSED
  test_credential_login_url_is_separately_scope_checked  PASSED
  test_http_probes_do_not_follow_unapproved_redirect_even_in_injected_client  PASSED
  test_web_probes_preserve_unselected_query_fields[SQLInjectionProbe]  PASSED
  test_web_probes_preserve_unselected_query_fields[XSSProbe]  PASSED
  test_web_probes_preserve_unselected_query_fields[PathTraversalProbe]  PASSED
  test_path_traversal_payload_never_escapes_path_only_approval  PASSED
  test_credential_routing_headers_are_refused_before_request[headers0]  PASSED
  test_credential_routing_headers_are_refused_before_request[headers1]  PASSED
  test_credential_routing_headers_are_refused_before_request[headers2]  PASSED
  test_credential_routing_headers_are_refused_before_request[headers3]  PASSED
# tests/unit/test_sqlmap_integration.py
  test_registry_discovers_all_three_tools_and_modules  PASSED
  test_sqlmap_version_and_disconnect  PASSED
  test_sqlmap_missing_binary_is_unavailable  PASSED
  test_disabled_and_missing_binary_are_fail_soft  PASSED
  test_get_detection_and_evidence_are_normalized  PASSED
  test_safe_arguments_and_private_auth_request  PASSED
  test_header_alias_parameters_do_not_select_headers[cookie-GET]  PASSED
  test_header_alias_parameters_do_not_select_headers[cookie-POST]  PASSED
  test_header_alias_parameters_do_not_select_headers[COOKIE-GET]  PASSED
  test_header_alias_parameters_do_not_select_headers[COOKIE-POST]  PASSED
  test_header_alias_parameters_do_not_select_headers[host-GET]  PASSED
  test_header_alias_parameters_do_not_select_headers[host-POST]  PASSED
  test_header_alias_parameters_do_not_select_headers[ua-GET]  PASSED
  test_header_alias_parameters_do_not_select_headers[ua-POST]  PASSED
  test_header_alias_parameters_do_not_select_headers[useragent-GET]  PASSED
  test_header_alias_parameters_do_not_select_headers[useragent-POST]  PASSED
  test_header_alias_parameters_do_not_select_headers[user-agent-GET]  PASSED
  test_header_alias_parameters_do_not_select_headers[user-agent-POST]  PASSED
  test_header_alias_parameters_do_not_select_headers[ref-GET]  PASSED
  test_header_alias_parameters_do_not_select_headers[ref-POST]  PASSED
  test_header_alias_parameters_do_not_select_headers[referer-GET]  PASSED
  test_header_alias_parameters_do_not_select_headers[referer-POST]  PASSED
  test_header_alias_parameters_do_not_select_headers[referrer-GET]  PASSED
  test_header_alias_parameters_do_not_select_headers[referrer-POST]  PASSED
  test_header_alias_can_be_only_parameter  PASSED
  test_negative_requires_every_selected_parameter_to_have_a_completed_result  PASSED
  test_positive_detection_reports_other_skipped_parameters  PASSED
  test_no_parameters_skips_before_connect  PASSED
  test_negative_is_not_a_guarantee_of_safety  PASSED
  test_exit_zero_without_completed_result_is_inconclusive[]  PASSED
  test_exit_zero_without_completed_result_is_inconclusive[[CRITICAL] unable to connect to the target URL]  PASSED
  test_exit_zero_without_completed_result_is_inconclusive[sqlmap failed]  PASSED
  test_nonzero_exit_is_error_and_cleans_up  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[file:///etc/passwd?id=1]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://user:password@127.0.0.1/test?id=1]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1:99999/test?id=1]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1/test?id=1#fragment]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1/test?id=1*]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1/test?id=1%2A]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1/test?id=1%252A]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1/approved/%252e%252e/private?id=1]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1/approved%5Cprivate?id=1]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1/test?id=%0d%0aHost:evil]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1/test?id=1\r\nHost:evil]  PASSED
  test_unsafe_urls_or_parameter_names_are_refused[http://127.0.0.1/test?--os-shell=1]  PASSED
  test_scope_substring_spoof_is_rejected_before_tool  PASSED
  test_implicit_default_port_must_be_in_scope  PASSED
  test_scope_and_exclusion_refuse_out_of_scope_before_tool  PASSED
  test_hostname_with_ip_exclusion_is_refused_without_running_tool[127.0.0.1]  PASSED
  test_hostname_with_ip_exclusion_is_refused_without_running_tool[127.0.0.0/8]  PASSED
  test_hostname_with_ip_exclusion_is_refused_without_running_tool[http://127.0.0.1:8000/private]  PASSED
  test_hostname_with_ip_exclusion_is_refused_without_running_tool[::1]  PASSED
  test_encoded_path_cannot_bypass_a_path_only_exclusion  PASSED
  test_wildcard_exclusion_is_refused_rather_than_ignored  PASSED
  test_literal_ip_in_excluded_network_is_refused[127.0.0.1]  PASSED
  test_literal_ip_in_excluded_network_is_refused[[::ffff:127.0.0.1]]  PASSED
  test_unrelated_network_exclusion_allows_approved_literal_ip  PASSED
  test_qualified_ip_exclusion_preserves_path_boundary  PASSED
  test_configured_testing_window_is_refused_until_enforced[window0]  PASSED
  test_configured_testing_window_is_refused_until_enforced[window1]  PASSED
  test_scope_path_is_not_approved_by_a_query_string  PASSED
  test_post_and_higher_level_require_impact_authorization  PASSED
  test_authorized_post_form_and_level  PASSED
  test_unsupported_techniques_never_launch_scan[U]  PASSED
  test_unsupported_techniques_never_launch_scan[T]  PASSED
  test_unsupported_techniques_never_launch_scan[S]  PASSED
  test_unsupported_techniques_never_launch_scan[BEUSTQ]  PASSED
  test_unsupported_techniques_never_launch_scan[--dump]  PASSED
  test_unsupported_techniques_never_launch_scan[]  PASSED
  test_unsafe_headers_never_launch_scan[headers0]  PASSED
  test_unsafe_headers_never_launch_scan[headers1]  PASSED
  test_unsafe_headers_never_launch_scan[headers2]  PASSED
  test_arbitrary_options_are_refused_before_connect  PASSED
  test_unknown_parameter_is_refused_before_connect  PASSED
  test_unrequested_or_malformed_summary_is_inconclusive  PASSED
  test_timeout_and_cancellation_cleanup  PASSED
  test_real_subprocess_is_reaped_on_timeout_and_cancellation  PASSED
  test_three_tools_coexist_in_one_sequential_plan  PASSED
  test_different_tools_in_independent_parallel_engagements  PASSED
  test_independent_parallel_scans_have_isolated_workdirs_and_state  PASSED
# tests/unit/test_public_tool_results.py
  test_help_and_missing_confirmation_never_need_dependencies_or_change_data  PASSED
  test_cli_rejects_arbitrary_targets  PASSED
  test_sqlmap_guard_accepts_only_the_precise_request_and_arguments  PASSED
  test_nmap_guard_refuses_extra_or_changed_arguments_before_delegate  PASSED
  test_rate_limit_is_recorded_before_scan_and_rejects_invalid_history  PASSED
  test_failed_latest_keeps_previous_real_capture_clearly_dated  PASSED
  test_three_real_tool_report_uses_saved_local_capture  PASSED
  test_compact_framework_view_is_derived_from_captured_finding  PASSED
  test_nmap_pdf_excerpt_preserves_selected_real_xml_values  PASSED
  test_local_metasploit_result_does_not_become_a_public_capture  PASSED
  test_renderer_escapes_untrusted_output_inside_long_fences  PASSED
  test_registered_tools_are_covered_and_pdf_matches_source_and_data  PASSED
  test_framework_collection_uses_guarded_profiles_without_real_network  PASSED
  test_failed_refresh_is_recorded_without_erasing_prior_success  PASSED
  test_explicit_all_refresh_runs_two_profiles_and_rebuilds  PASSED
  test_ipv6_metasploit_capture_is_shown_only_as_a_local_check  PASSED
  test_new_genuine_local_metasploit_capture_never_becomes_a_public_result  PASSED
```

## 7. Files these outputs are saved in

| File | What it is |
|---|---|
| `docs/all_tools_result/run-all-tools.json` | Saved output of the latest all-tools run (15:55 UTC) |
| `docs/all_tools_result/run-all-tools-2026-11-02-1414.json` | Saved output of the earlier 14:14 UTC run, kept for history |
| `docs/real_results.json` | Saved results, labelled PUBLIC, LOCAL LAB and SIMULATED |
| `docs/real result.pdf` | Real-results PDF built from `real_results.json` |

## 8. Limits

- The public runs are one-time captures. They count toward the daily limits (Nmap 10 and sqlmap 6 per 24 hours in this project).
- Metasploit was tested on a temporary listener on this computer only. No public site allows it.
- Mac and Windows were not used for these runs. Results are from a Linux sandbox.
- The password for the Metasploit daemon was not written into any log or output file.
- The three external tools are disabled by default in the app configuration. The runs above enabled them on purpose, for testing only.
- The site `testphp.vulnweb.com` was not used. It was unreachable from the test machine.
