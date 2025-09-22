# push_to_github.ps1 — helper script
param(
  [Parameter(Mandatory=$true)][string]$RepoUrl
)
git init
git add .
git commit -m "Initial commit: Success Dynamics Accountability Chart v3"
git branch -M main
git remote add origin $RepoUrl
git push -u origin main
