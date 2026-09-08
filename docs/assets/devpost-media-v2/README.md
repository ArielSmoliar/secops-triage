# Devpost media v2

Use thumbnail.png as the project cover. Add the numbered gallery images in order; CAPTIONS.md contains the corresponding Devpost captions. All five PNGs are 1536 × 1024 (3:2), each below 5 MB. Captions are at most 140 characters.

The cover is conceptual AI-generated artwork. The gallery uses the existing native demo artwork, containing magnified excerpts from the recorded scripted run with synthetic evidence. It preserves the source content and adds a title, caption and disclosure footer. The automated operator handoff is not human acceptance. No AWS deployment or new investigation/model run occurred.

Generation prompt: PROMPT.md. Gallery provenance and hashes: captions.json. Reproduce on macOS with Pillow and system Arial fonts:

python ops/demo_video/gallery.py --artwork data/demo-video-20260908/artwork-clarity-a --output /tmp/secops-gallery-new

Use a fresh output directory. Original demo artwork and previous media remain unchanged. New assets have not been uploaded to Devpost.
