$TaskName = "BabataV5Bot"
$BotDir = "C:\TradingBot_v3\smc_v3_core"
$User = "$env:USERDOMAIN\$env:USERNAME"

$Action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c C:\TradingBot_v3\smc_v3_core\START_BOT.cmd" -WorkingDirectory $BotDir
$Trigger  = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -User $User -RunLevel Highest
Write-Host "Installed Scheduled Task: $TaskName (runs as $User at logon)"
