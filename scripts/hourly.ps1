# 매시간 자동 빌드 + push.
# - 평일 09-16시 KST 만 실행 (그 외는 즉시 종료)
# - 한국 공휴일은 holidays 패키지로 스킵
# - 종목별 빌드 후 HTML diff 가 있을 때만 commit / push

$ErrorActionPreference = "Stop"
Set-Location "C:\pjt\reporter"

$logDir = "C:\pjt\reporter\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("hourly_" + (Get-Date -Format "yyyy-MM") + ".log")

function Write-Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $logFile -Value $line -Encoding utf8
    Write-Output $line
}

# ─── 실행 가드 ────────────────────────────────────────────────────────
$now = Get-Date
$dow = $now.DayOfWeek
$hour = $now.Hour

if ($dow -eq "Saturday" -or $dow -eq "Sunday") {
    Write-Log "skip: weekend ($dow)"
    exit 0
}

if ($hour -lt 9 -or $hour -gt 16) {
    Write-Log "skip: outside market hours (hour=$hour)"
    exit 0
}

# 한국 공휴일 (holidays 패키지)
$year = $now.Year
$holidayCheck = py -3.11 -c "import holidays, datetime; kr=holidays.KR(years=[$year]); print('1' if datetime.date.today() in kr else '0')"
if ($holidayCheck.Trim() -eq "1") {
    Write-Log "skip: KR holiday"
    exit 0
}

# ─── 빌드 ─────────────────────────────────────────────────────────────
$tickers = @("329180", "456160")  # HD현대중공업, 지투지바이오
foreach ($t in $tickers) {
    Write-Log "build start: $t"
    try {
        py -3.11 -m src.main $t 2>&1 | ForEach-Object { Write-Log "  [$t] $_" }
        Write-Log "build done: $t"
    } catch {
        Write-Log "build FAILED: $t — $_"
    }
}

# ─── git status / diff ────────────────────────────────────────────────
git add data/output 2>&1 | Out-Null
$staged = git diff --cached --name-only
if ([string]::IsNullOrWhiteSpace($staged)) {
    Write-Log "no html diff — skip commit"
    exit 0
}
Write-Log "staged files:`n$staged"

# ─── commit + push ────────────────────────────────────────────────────
$msg = "auto: hourly refresh $($now.ToString('yyyy-MM-dd HH:mm')) KST"
git commit -m $msg 2>&1 | ForEach-Object { Write-Log "  $_" }
git push origin main 2>&1 | ForEach-Object { Write-Log "  $_" }
Write-Log "pushed."
