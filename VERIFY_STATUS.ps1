Write-Host "== python.exe processes =="
& tasklist /FI "IMAGENAME eq python.exe"

Write-Host "\n== bot.log tail =="
if (Test-Path C:\TradingBot\bot.log) {
  Get-Content C:\TradingBot\bot.log -Tail 60
} else {
  Write-Host "C:\TradingBot\bot.log not found"
}

Write-Host "\n== bot.err.log tail =="
if (Test-Path C:\TradingBot\bot.err.log) {
  Get-Content C:\TradingBot\bot.err.log -Tail 60
} else {
  Write-Host "C:\TradingBot\bot.err.log not found"
}
