"""Generate original title/architecture/end graphics and transparent video labels."""
from pathlib import Path
import argparse,json,textwrap
from PIL import Image,ImageDraw,ImageFont
BG='#10232b';INK='#f5f3eb';MUTED='#bac9cc';TEAL='#88d7c2';LINE='#35535c';PANEL='#19333c'
REG='/System/Library/Fonts/Supplemental/Arial.ttf';BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def font(n,bold=False):return ImageFont.truetype(BOLD if bold else REG,n)
def drawtext(d,xy,text,size=30,color=INK,bold=False):d.text(xy,text,font=font(size,bold),fill=color,spacing=16)
def box(d,xy,heading,body):
 d.rounded_rectangle(xy,radius=18,fill=PANEL,outline=LINE,width=2)
 drawtext(d,(xy[0]+28,xy[1]+22),heading,31,TEAL,True)
 drawtext(d,(xy[0]+28,xy[1]+75),body,25,MUTED)
def main():
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);args=p.parse_args();out=args.root;out.mkdir(exist_ok=False,parents=True)
 story=json.loads(Path('ops/demo_video/story.json').read_text())
 for i,s in enumerate(story['scenes']):
  base=Image.new('RGBA',(1920,1080),BG);d=ImageDraw.Draw(base)
  drawtext(d,(192,35),s['heading'],40,INK,True);drawtext(d,(192,90),s['subheading'],23,TEAL)
  d.rounded_rectangle((187,135,1733,925),radius=10,fill=BG,outline=LINE,width=2)
  # Clear the window for screen footage. Labels are editorial, outside the app.
  base.paste((0,0,0,0),(192,140,1728,920))
  drawtext(d,(192,1044),'Recorded scripted demo  •  Synthetic evidence  •  OpenAI-generated narration',19,MUTED)
  drawtext(d,(1410,1044),f'SecOps Triage  /  {i+1:02} of 08',19,MUTED)
  base.save(out/(s['id']+'-overlay.png'))
 for id in ('01-intro','07-architecture','08-close'):
  im=Image.new('RGB',(1536,780),BG);d=ImageDraw.Draw(im)
  if id=='01-intro':
   drawtext(d,(65,64),'SECURITY OPERATIONS  /  PROFESSIONAL AGENTS',21,TEAL,True)
   drawtext(d,(60,155),'SecOps\nTriage',110,INK,True)
   drawtext(d,(65,430),'Evidence for the\nnext analyst decision.',43,MUTED)
   for n,(a,b) in enumerate([('01  Incident','An existing SIEM incident'),('02  Investigation','Four scoped Strands tools'),('03  Evidence','Sources, citations and uncertainty'),('04  Handoff','A local record for human review')]):
    y=72+n*161;box(d,(840,y,1480,y+136),a,b)
   drawtext(d,(65,674),'Recorded prototype • Synthetic evidence',25,TEAL)
  elif id=='07-architecture':
   drawtext(d,(50,36),'THIS RECORDING: LOCAL',25,TEAL,True)
   box(d,(50,95,785,239),'Strands Agents SDK','Provider: scripted fixture\nNo live model inference in this recording')
   box(d,(50,279,785,450),'Four scoped investigation tools','Incident  •  Entity  •  Activity  •  Related cases\nRead-only access to a synthetic snapshot')
   box(d,(50,490,785,665),'Host controls and local storage','Scope  •  Integrity  •  Evidence  •  Decisions\nSQLite and retained artifacts')
   for y in (247,458):drawtext(d,(400,y),'↓',28,TEAL)
   drawtext(d,(850,36),'SEPARATE AWS VERIFICATION',25,TEAL,True)
   box(d,(850,95,1485,515),'Verified in Ohio, September 8','EC2: private scripted execution\n\nEBS: encrypted evidence storage\n\nSSM: operator access\n\nCloudWatch: verified event delivery')
   drawtext(d,(875,549),'Host stopped; evidence retained.',27,INK,True)
   drawtext(d,(875,605),'UI has not been deployed to AWS.',25,MUTED)
   drawtext(d,(50,716),'Bedrock, AgentCore and live security connectors are not implemented.',24,MUTED)
  else:
   drawtext(d,(65,55),'EVIDENCE FIRST.',85,INK,True)
   drawtext(d,(65,159),'Judgment stays with the analyst.',48,TEAL,True)
   box(d,(65,275,725,458),'310 tests passed','14 browser checks  •  Frozen-source verification\nTechnical prototype; not production validation')
   box(d,(770,275,1475,458),'Limits remain visible','Scripted findings fail the completeness rubric\nLive-model and human validation remain open')
   drawtext(d,(65,540),'SecOps Triage',53,INK,True)
   drawtext(d,(65,622),'github.com/ArielSmoliar/secops-triage',34,TEAL)
   drawtext(d,(65,699),'Built with Strands Agents SDK  /  Agents for Humans',25,MUTED)
  im.save(out/(id+'.png'))
if __name__=='__main__':main()
