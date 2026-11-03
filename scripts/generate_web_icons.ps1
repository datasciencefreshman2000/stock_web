# Generate the app's simple vault icon without external downloads or packages.
Add-Type -AssemblyName System.Drawing
$iconDirectory = Join-Path $PSScriptRoot '../frontend/public/icons'
New-Item -ItemType Directory -Force -Path $iconDirectory | Out-Null
foreach ($size in @(180, 192, 512)) {
    $bitmap = New-Object System.Drawing.Bitmap($size, $size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#0b1020'))
    $pen = New-Object System.Drawing.Pen([System.Drawing.ColorTranslator]::FromHtml('#7dd3fc'), ($size * 0.025))
    $graphics.DrawRectangle($pen, ($size * 0.22), ($size * 0.22), ($size * 0.56), ($size * 0.56))
    $graphics.DrawEllipse($pen, ($size * 0.36), ($size * 0.36), ($size * 0.28), ($size * 0.28))
    $graphics.DrawLine($pen, ($size * 0.5), ($size * 0.39), ($size * 0.5), ($size * 0.61))
    $graphics.DrawLine($pen, ($size * 0.39), ($size * 0.5), ($size * 0.61), ($size * 0.5))
    $name = if ($size -eq 180) { 'apple-touch-icon.png' } else { "icon-$size.png" }
    $bitmap.Save((Join-Path $iconDirectory $name), [System.Drawing.Imaging.ImageFormat]::Png)
    $pen.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
}
