# Deployment Guide -- Windows VPS

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Windows | 10/11 or Server 2019+ | `winver` |
| Python | 3.11+ | `python --version` |
| Git | Any recent | `git --version` |
| PowerShell | 5.1+ | `$PSVersionTable.PSVersion` |
| TWS or IB Gateway | Latest | Running on port 4002 |

---

## One-Command Deploy

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
.\deploy\windows\deploy.ps1
```

Or with custom paths:

```powershell
.\deploy\windows\deploy.ps1 -BotDir "D:\bots\audjpy-v2" -Branch "main"
```

---

## TWS API Configuration

In TWS: **File -> Global Configuration -> API -> Settings**

| Setting | Value |
|---|---|
| Enable ActiveX and Socket Clients | Checked |
| Socket port | 4002 (paper) |
| Allow connections from localhost only | Checked |
| Read-Only API | Unchecked |

---

## Local Config

After first deploy, edit `config/settings.local.yaml`:

```yaml
ibkr:
  port: 4002
  client_id: 1

safety:
  paper_submit_orders: false
```

---

## Troubleshooting

**Python not recognized** -- Reinstall Python, check "Add to PATH"

**Cannot connect to TWS** -- Check API settings, verify port 4002

**Activation policy error** -- Run: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force`

**Tests failing** -- Check test output; usually a config or import path issue

**No candles** -- AUDJPY may need market data subscription in TWS

See full guide: [DEPLOYMENT.md](DEPLOYMENT.md)
