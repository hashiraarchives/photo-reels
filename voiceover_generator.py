"""
AAP - Actress Actor and Pinups
Personalized Voiceover Generator

Uses Gemini AI to write a warm, calming intro script personalized
to each video's content, then synthesizes it with edge-tts.
Designed for the 65+ audience — relaxed, nostalgic, inviting.
"""

import os
import re
import json
import asyncio
import logging
from typing import Optional, Dict
import config

logger = logging.getLogger('AAP-Voiceover')

# Warm, mature voices suitable for nostalgic content
VOICE_OPTIONS = [
    "en-US-GuyNeural",          # Warm male narrator
    "en-US-JennyNeural",        # Friendly female narrator
    "en-GB-RyanNeural",         # Distinguished British male
    "en-GB-SoniaNeural",        # Elegant British female
]


def _build_script_prompt(metadata: Dict) -> str:
    """Build a Gemini prompt to generate a voiceover script."""
    names = []
    captions = []

    for img in metadata.get('images', [])[:10]:
        title = img.get('title', '')
        caption = img.get('generated_caption', '')
        if title:
            names.append(title[:60])
        if caption:
            captions.append(caption[:80])

    image_count = metadata.get('image_count', len(metadata.get('images', [])))
    theme = metadata.get('theme', 'Classic Hollywood').replace('_', ' ')

    sample_content = '\n'.join(captions[:6]) if captions else theme

    return f"""You write warm, calming voiceover intros for a vintage Hollywood photo channel.
The audience is 55-75 year olds who love nostalgia and Old Hollywood glamour.

Video theme: {theme}
Number of photos: {image_count}
Sample content from this video:
{sample_content}

Write a SHORT voiceover intro (2-4 sentences, max 40 words total).
Rules:
- Tone: warm, relaxed, like a trusted friend inviting you to sit down and reminisce
- Reference specific content from this video (names, era, theme)
- End with an inviting phrase like "sit back and enjoy" or "let's take a journey"
- Do NOT mention subscribing, liking, or any call-to-action
- Do NOT use exclamation marks — keep it gentle
- Write ONLY the script text, nothing else"""


def generate_voiceover_script(metadata: Dict) -> Optional[str]:
    """Use Gemini to write a personalized voiceover script."""
    try:
        from google import genai
    except ImportError:
        logger.error("google-genai not installed")
        return None

    api_key = getattr(config, 'GEMINI_API_KEY', None)
    if not api_key:
        logger.warning("No GEMINI_API_KEY — skipping voiceover script generation")
        return None

    prompt = _build_script_prompt(metadata)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=prompt,
        )
        script = response.text.strip()

        # Clean up: remove quotes, markdown, etc.
        script = script.strip('"\'')
        script = re.sub(r'^```.*\n?', '', script)
        script = re.sub(r'\n?```$', '', script)
        script = script.strip()

        # Safety check: script should be short and sweet
        if len(script) > 300:
            script = script[:297] + "..."
        if len(script) < 10:
            return None

        logger.info(f"Generated voiceover script: {script}")
        return script

    except Exception as e:
        logger.error(f"Gemini voiceover script error: {e}")
        return None


async def _synthesize_async(text: str, output_path: str, voice: str) -> bool:
    """Synthesize speech using edge-tts."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate="-10%", pitch="-5Hz")
    await communicate.save(output_path)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


def synthesize_voiceover(script: str, output_path: str) -> Optional[str]:
    """
    Convert text script to speech audio file using edge-tts.

    Args:
        script: The voiceover text
        output_path: Where to save the MP3

    Returns:
        Path to the audio file, or None on failure
    """
    import random
    voice = random.choice(VOICE_OPTIONS)
    logger.info(f"Synthesizing voiceover with voice: {voice}")

    try:
        asyncio.run(_synthesize_async(script, output_path, voice))

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.info(f"Voiceover saved: {output_path}")
            return output_path
        else:
            logger.error("Voiceover file too small or missing")
            return None

    except Exception as e:
        logger.error(f"edge-tts synthesis error: {e}")
        return None


def generate_voiceover(metadata: Dict, output_dir: str = None) -> Optional[str]:
    """
    Full pipeline: generate script with Gemini, synthesize with edge-tts.

    Args:
        metadata: Video metadata dict
        output_dir: Directory for the output audio file

    Returns:
        Path to voiceover audio file, or None
    """
    if not output_dir:
        output_dir = config.OUTPUT_FOLDER

    # Step 1: Generate personalized script
    script = generate_voiceover_script(metadata)
    if not script:
        logger.warning("Could not generate voiceover script, skipping")
        return None

    print(f"  Voiceover script: \"{script}\"")

    # Step 2: Synthesize to audio
    output_path = os.path.join(output_dir, "voiceover_intro.mp3")
    result = synthesize_voiceover(script, output_path)

    return result


if __name__ == "__main__":
    # Quick test
    sample_metadata = {
        'theme': 'Classic_Hollywood_Glamour',
        'image_count': 45,
        'images': [
            {'title': 'Marilyn Monroe portrait', 'generated_caption': 'Marilyn Monroe in a glamorous studio portrait from 1953'},
            {'title': 'Audrey Hepburn', 'generated_caption': 'Audrey Hepburn wearing her iconic little black dress'},
            {'title': 'Grace Kelly', 'generated_caption': 'Grace Kelly at a Hollywood premiere in the 1950s'},
        ]
    }

    result = generate_voiceover(sample_metadata, output_dir=".")
    if result:
        print(f"\nSuccess! Voiceover saved to: {result}")
    else:
        print("\nFailed to generate voiceover")
