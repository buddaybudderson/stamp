#!/usr/bin/env sh
# Build the arXiv source from the Markdown. Edit stamp-report.md, never the .tex.
#   sh paper/build.sh            -> paper/stamp-report.tex (upload this to arXiv or Overleaf)
#   sh paper/build.sh pdf        -> also paper/stamp-report.pdf, if a LaTeX engine is installed
set -e
cd "$(dirname "$0")"
pandoc stamp-report.md -s -o stamp-report.tex \
  -V documentclass=article -V geometry:margin=1in -V fontsize=11pt -V colorlinks=true \
  -V linkcolor=blue -V urlcolor=blue -V header-includes='\sloppy'
echo "wrote paper/stamp-report.tex"
if [ "$1" = "pdf" ]; then
  pdflatex -interaction=nonstopmode -halt-on-error stamp-report.tex >/dev/null && pdflatex -interaction=nonstopmode -halt-on-error stamp-report.tex >/dev/null
  echo "wrote paper/stamp-report.pdf"
  cp stamp-report.pdf ../docs/paper/stamp-report.pdf
  echo "copied it to docs/paper/ (the site's copy; keep them identical)"
fi
