"""Lay out verified, code-generated demo artwork as captioned 3:2 gallery cards."""
from pathlib import Path
import argparse,json,hashlib,textwrap
from PIL import Image,ImageDraw,ImageFont

def main():
 p=argparse.ArgumentParser();p.add_argument('--artwork',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 items=[
  ('01-investigation','03-trace','Gather the context','Four scoped Strands tools gather nine evidence reads into one inspectable packet. Recorded scripted execution; synthetic evidence.'),
  ('02-email-comparison','04-messages','Separate training from the suspicious follow-up','The first email is approved training. The second has a different clicked link; that training approval does not cover it.'),
  ('03-exact-evidence','05-evidence','Inspect the evidence behind investigation','The exact-link citation exposes the synthetic intelligence verdict, while host policy recommends further investigation.'),
  ('04-analyst-handoff','06-handoff','Preserve a concrete next step','An automated demo operator saves the reason, missing context and next action with the evidence packet. The source SIEM stays unchanged.')]
 fontroot=Path('/System/Library/Fonts/Supplemental');font=lambda size,bold=False:ImageFont.truetype(str(fontroot/('Arial Bold.ttf' if bold else 'Arial.ttf')),size)
 records=[]
 for name,sid,title,caption in items:
  source=a.artwork/(sid+'-focus.png');content=Image.open(source).convert('RGB')
  if content.size!=(1536,780):raise ValueError('unexpected native artwork size')
  im=Image.new('RGB',(1536,1024),'#10232b');d=ImageDraw.Draw(im)
  d.text((48,34),title,font=font(39,True),fill='#f5f3eb')
  im.paste(content.resize((1456,739),Image.Resampling.LANCZOS),(40,109))
  d.line((48,864,1488,864),fill='#35535c',width=2)
  lines=[];line=''
  for word in caption.split():
   trial=(line+' '+word).strip()
   if d.textlength(trial,font=font(27))>1440:lines.append(line);line=word
   else:line=trial
  if line:lines.append(line)
  if len(lines)>2 or len(caption)>140:raise ValueError('caption exceeds layout or Devpost limit')
  for i,line in enumerate(lines):d.text((48,884+i*36),line,font=font(27),fill='#bac9cc')
  d.text((48,982),'SECOPS TRIAGE  /  Recorded scripted demo  /  Synthetic evidence',font=font(19),fill='#88d7c2')
  file=a.output/(name+'.png');im.save(file,optimize=True)
  records.append({'file':file.name,'caption':caption,'title':title,'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'bytes':file.stat().st_size})
 (a.output/'captions.json').write_text(json.dumps(records,indent=2)+'\n')
 (a.output/'CAPTIONS.md').write_text('# Devpost gallery captions\n\n'+''.join('## '+x['file']+'\n\n'+x['caption']+'\n\n' for x in records))
if __name__=='__main__':main()
