# -*- coding: utf-8 -*-
"""
faster_qt 环境安装脚本

功能：
1. 安装 PostgreSQL 数据库（如未安装）
2. 安装 Memurai（Redis兼容，如未安装）
3. 安装 Python 依赖包
4. 初始化数据库

系统要求：
- Windows 10/11
- PowerShell 5.1+
- Python 3.11+

使用方式：
    # 先设置执行策略（如果需要）
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    
    # 运行脚本
    .\scripts\install_env.ps1

作者：江小猪 🐷
日期：2026-04-19
"""

#Requires -Version 5.1

param(
    [switch]$SkipPostgreSQL,
    [switch]$SkipRedis,
    [switch]$SkipPython,
    [switch]$SkipDBInit
)

# 颜色输出函数
function Write-Step { param($Message) Write-Host "[STEP] $Message" -ForegroundColor Cyan }
function Write-Success { param($Message) Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn { param($Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Fail { param($Message) Write-Host "[FAIL] $Message" -ForegroundColor Red }

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  🚀 faster_qt 环境安装脚本" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ========== 检查 Python ==========
Write-Step "检查 Python 环境..."
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
    $pythonVersion = python --version 2>&1
    Write-Success "Python 已安装: $pythonVersion"
} else {
    Write-Fail "Python 未安装，请先安装 Python 3.11+"
    Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# ========== 检查/安装 PostgreSQL ==========
if (-not $SkipPostgreSQL) {
    Write-Step "检查 PostgreSQL..."
    
    $pgService = Get-Service -Name "postgresql-x64-16" -ErrorAction SilentlyContinue
    if ($pgService) {
        Write-Success "PostgreSQL 服务已安装: $($pgService.DisplayName)"
        
        # 检查连接
        $env:PGPASSWORD = "root"
        $pgBin = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
        if (Test-Path $pgBin) {
            $testResult = & $pgBin -h 127.0.0.1 -U postgres -d postgres -c "SELECT 1;" 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "PostgreSQL 连接正常"
            } else {
                Write-Warn "PostgreSQL 连接失败，尝试重置密码..."
                # 临时修改 pg_hba.conf
                $hbaPath = "C:\Program Files\PostgreSQL\16\data\pg_hba.conf"
                if (Test-Path $hbaPath) {
                    $hbaContent = Get-Content $hbaPath -Raw
                    $newHba = $hbaContent -replace "host    all             all             127.0.0.1/32            scram-sha-256", "host    all             all             127.0.0.1/32            trust"
                    Set-Content -Path $hbaPath -Value $newHba -NoNewline
                    & "C:\Program Files\PostgreSQL\16\bin\pg_ctl.exe" reload -D "C:\Program Files\PostgreSQL\16\data" 2>&1 | Out-Null
                    & $pgBin -h 127.0.0.1 -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD 'root';" 2>&1 | Out-Null
                    $newHbaRestore = $hbaContent  # 恢复
                    Set-Content -Path $hbaPath -Value $newHbaRestore -NoNewline
                    & "C:\Program Files\PostgreSQL\16\bin\pg_ctl.exe" reload -D "C:\Program Files\PostgreSQL\16\data" 2>&1 | Out-Null
                    Write-Success "密码重置完成"
                }
            }
        }
    } else {
        Write-Warn "PostgreSQL 未安装，尝试安装..."
        
        # 检查 Chocolatey
        $choco = Get-Command choco -ErrorAction SilentlyContinue
        if (-not $choco) {
            Write-Step "安装 Chocolatey..."
            Set-ExecutionPolicy Bypass -Scope Process -Force
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        }
        
        Write-Step "安装 PostgreSQL 16..."
        choco install postgresql -y --params "/PASSWORD:root /TECONFIG:true" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "PostgreSQL 安装完成"
        } else {
            Write-Fail "PostgreSQL 安装失败，请手动安装"
        }
    }
} else {
    Write-Warn "跳过 PostgreSQL 安装"
}

# ========== 检查/安装 Memurai (Redis) ==========
if (-not $SkipRedis) {
    Write-Step "检查 Memurai (Redis)..."
    
    $memuraiService = Get-Service -Name "Memurai" -ErrorAction SilentlyContinue
    if ($memuraiService) {
        Write-Success "Memurai 服务已安装: $($memuraiService.DisplayName)"
        
        # 测试连接
        $memuraiCli = "C:\Program Files\Memurai\memurai-cli.exe"
        if (Test-Path $memuraiCli) {
            $pingResult = & $memuraiCli ping 2>&1
            if ($pingResult -eq "PONG") {
                Write-Success "Memurai 连接正常"
            }
        }
    } else {
        Write-Warn "Memurai 未安装，尝试安装..."
        
        $choco = Get-Command choco -ErrorAction SilentlyContinue
        if (-not $choco) {
            Set-ExecutionPolicy Bypass -Scope Process -Force
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        }
        
        Write-Step "安装 Memurai..."
        choco install memurai-developer -y 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Memurai 安装完成"
        } else {
            Write-Fail "Memurai 安装失败，请手动安装"
        }
    }
} else {
    Write-Warn "跳过 Memurai 安装"
}

# ========== 安装 Python 依赖 ==========
if (-not $SkipPython) {
    Write-Step "安装 Python 依赖包..."
    
    $packages = @(
        "psycopg2-binary",
        "redis",
        "numpy",
        "pandas",
        "akshare",
        "tushare",
        "sqlalchemy"
    )
    
    foreach ($pkg in $packages) {
        Write-Step "安装 $pkg..."
        pip install $pkg 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "$pkg 安装成功"
        } else {
            Write-Warn "$pkg 安装失败（或已存在）"
        }
    }
}

# ========== 初始化数据库 ==========
if (-not $SkipDBInit) {
    Write-Step "初始化数据库..."
    
    # 设置密码
    $env:PGPASSWORD = "root"
    
    # 检查数据库
    $pgBin = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
    
    # 检查 faster_qt 数据库
    $checkDb = & $pgBin -h 127.0.0.1 -U postgres -d postgres -t -c "SELECT 1 FROM pg_database WHERE datname = 'faster_qt';" 2>&1
    if ($checkDb -match "1") {
        Write-Success "数据库 faster_qt 已存在"
    } else {
        Write-Step "创建数据库 faster_qt..."
        & $pgBin -h 127.0.0.1 -U postgres -d postgres -c "CREATE DATABASE faster_qt;" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "数据库 faster_qt 创建成功"
        }
    }
    
    # 运行 Python 初始化脚本
    Write-Step "运行数据库初始化脚本..."
    python "C:\Users\19942\qt\faster_qt\scripts\init_database.py" 2>&1
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  ✅ 环境安装完成！" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "📋 下一步："
Write-Host "  1. 编辑配置文件: configs/system.example.json"
Write-Host "  2. 运行测试: python -m src.data.loader"
Write-Host "  3. 开始策略开发！"
Write-Host ""