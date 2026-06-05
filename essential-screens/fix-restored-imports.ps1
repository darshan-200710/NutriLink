# Fix imports in restored files
$files = @(
    "src/components/Header.tsx",
    "src/pages/Landing.tsx",
    "src/pages/SignIn.tsx",
    "src/pages/SignUp.tsx",
    "src/pages/Capture.tsx",
    "src/pages/History.tsx",
    "src/pages/Statistics.tsx",
    "src/pages/Sync.tsx"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        $content = Get-Content $file -Raw
        
        # Determine relative path based on file location
        if ($file -like "*components/*") {
            $content = $content -replace 'from "@/lib/utils"', 'from "../lib/utils"'
            $content = $content -replace 'from "@/hooks/', 'from "../hooks/'
            $content = $content -replace 'from "@/components/', 'from "./'
        } else {
            # Pages directory
            $content = $content -replace 'from "@/lib/utils"', 'from "../lib/utils"'
            $content = $content -replace 'from "@/lib/api"', 'from "../lib/api"'
            $content = $content -replace 'from "@/hooks/', 'from "../hooks/'
            $content = $content -replace 'from "@/components/ui/', 'from "../components/ui/'
            $content = $content -replace 'from "@/components/', 'from "../components/'
        }
        
        Set-Content $file -Value $content -NoNewline
    }
}

Write-Host "Restored files updated with relative imports!"
