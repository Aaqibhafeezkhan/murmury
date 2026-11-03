#!/bin/zsh
# Plays a few questions through the Mac's speakers, as if the other side of a call asked them.
# Murmury hears the Mac's audio output, so this is a way to try it without a call:
#   1. start Murmury with docs/demo/q3-review.md as the document and press Start Listening
#   2. run: zsh docs/demo/ask.sh
VOICE=${VOICE:-Samantha}
PAUSE=${PAUSE:-12}

echo "First question in 3 seconds..."
sleep 3
for question in \
  "Why is SMB below plan in September?" \
  "What's your CAC payback right now?" \
  "How long is your runway?"; do
  echo "→ $question"
  say -v "$VOICE" "$question"
  sleep "$PAUSE"
done
