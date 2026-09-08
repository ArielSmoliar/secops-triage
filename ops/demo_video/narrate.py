"""One authorized narration batch. Never imports, consumes or extends investigation grants."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError('redirect refused')

def durable_bytes(path, value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(value)
        f.flush()
        os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def save(path,value):
    durable_bytes(path,json.dumps(value,indent=2).encode())

def require(condition,message):
    if not condition:raise ValueError(message)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--story',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--scene',action='append',choices=['01-intro','02-start','03-trace','04-messages','05-evidence','06-handoff','07-architecture','08-close'],help='Repeat to generate only selected owner-requested scenes')
    args=p.parse_args()
    story=json.loads(args.story.read_text())
    require(story['model']=='gpt-4o-mini-tts-2025-12-15' and story['voice']=='cedar','unexpected speech configuration')
    scenes=story['scenes']
    require(len(scenes)==8 and sum(x['seconds'] for x in scenes)==120,'eight scenes and two-minute target required')
    require(len({x['id'] for x in scenes})==8,'scene identities must be unique')
    require(all(x['id'].replace('-','').isalnum() and len(x['narration'])<1000 for x in scenes),'bounded text and safe scene IDs required')
    require(sum(len(x['narration']) for x in scenes)<5000,'batch text limit')
    require(len(story['voice_instructions'])<1000,'instructions limit')
    if args.scene:
        require(len(args.scene)==len(set(args.scene)),'duplicate scene selection')
        scenes=[x for x in scenes if x['id'] in args.scene]
    args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    save(args.output/'request-manifest.json',{'authorization':'Owner explicitly requested creating a two-minute demo video with OpenAI voice; narration only, no investigation inference or AWS authority.', 'model':story['model'],'voice':story['voice'],'max_requests':len(scenes),'scene_ids':[x['id'] for x in scenes],'automatic_retries':0,'story_sha256':hashlib.sha256(args.story.read_bytes()).hexdigest(),'rates_verified_20260908':{'text_usd_per_million_tokens':0.6,'audio_usd_per_million_tokens':12,'source':'https://developers.openai.com/api/docs/models/gpt-4o-mini-tts'},'billing':'Binary speech responses do not provide token usage; final billing is not asserted.'})
    # Reuse only the safe literal parser, never source a credentials file.
    from secops_triage.live import load_key
    key=os.environ.get('OPENAI_API_KEY') or load_key(Path('.env'))
    import certifi
    opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())))
    for scene in scenes:
        payload={'model':story['model'],'voice':story['voice'],'input':scene['narration'],'instructions':story['voice_instructions'],'response_format':'wav'}
        prefix=args.output/scene['id']
        save(prefix.with_suffix('.intent.json'),{'at':datetime.now(timezone.utc).isoformat(),'input_sha256':hashlib.sha256(scene['narration'].encode()).hexdigest(),'state':'dispatch_reserved','no_retry':True})
        request=urllib.request.Request('https://api.openai.com/v1/audio/speech',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        try:
            with opener.open(request,timeout=60) as response:
                audio=response.read(20_000_001)
                require(len(audio)<=20_000_000 and audio[:4]==b'RIFF' and audio[8:12]==b'WAVE','bounded WAV response required')
                request_id=response.headers.get('x-request-id')
            path=prefix.with_suffix('.wav')
            durable_bytes(path,audio)
            save(prefix.with_suffix('.result.json'),{'state':'completed','request_id':request_id,'audio_sha256':hashlib.sha256(audio).hexdigest(),'bytes':len(audio),'billing_status':'not returned'})
            print(scene['id']+' narration saved',flush=True)
        except BaseException as exc:
            save(prefix.with_suffix('.failure.json'),{'state':'failed_or_indeterminate','type':type(exc).__name__,'http_status':exc.code if isinstance(exc,urllib.error.HTTPError) else None,'automatic_retry':False,'remaining_batch_stopped':True})
            print('Narration stopped; failure preserved, no automatic retry.',file=sys.stderr)
            return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
