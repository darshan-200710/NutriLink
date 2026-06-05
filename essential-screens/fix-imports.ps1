# Fix all @/lib/utils imports in src/components/ui
Get-ChildItem -Path "src/components/ui" -Filter "*.tsx" -File | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $content = $content -replace 'from "@/lib/utils"', 'from "../../lib/utils"'
    $content = $content -replace 'from "@/hooks/use-mobile"', 'from "../../hooks/use-mobile"'
    $content = $content -replace 'from "@/hooks/use-toast"', 'from "../../hooks/use-toast"'
    $content = $content -replace 'from "@/components/ui/', 'from "./'
    Set-Content $_.FullName -Value $content -NoNewline
}

# Fix use-toast.ts separately
$useToastPath = "src/components/ui/use-toast.ts"
if (Test-Path $useToastPath) {
    $content = Get-Content $useToastPath -Raw
    $content = $content -replace 'from "@/hooks/use-toast"', 'from "../../hooks/use-toast"'
    Set-Content $useToastPath -Value $content -NoNewline
}

Write-Host "Import fixes applied successfully!"
