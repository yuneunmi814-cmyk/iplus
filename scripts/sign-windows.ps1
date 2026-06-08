param([Parameter(Mandatory=$true)][string]$FilePath)
# Windows code-signing placeholder. No-op until a certificate is configured.
# For real signing: signtool sign /fd SHA256 /tr <RFC3161 TSA> /td SHA256 /a "$FilePath"
if ($env:WINDOWS_CERTIFICATE) {
  Write-Host "Signing $FilePath ..."
  # signtool sign /f cert.pfx /p $env:WINDOWS_CERTIFICATE_PASSWORD /fd SHA256 "$FilePath"
} else {
  Write-Host "No WINDOWS_CERTIFICATE set — skipping signing for $FilePath (unsigned build)."
}
