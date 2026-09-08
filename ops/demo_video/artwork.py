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
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--spotlight',type=Path);args=p.parse_args();out=args.root;out.mkdir(exist_ok=False,parents=True)
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
   for n,(a,b) in enumerate([('01  First email','An approved security-training exercise'),('02  Suspicious follow-up','Different link; clicked and flagged malicious'),('03  Check the approval','Training scope names only the first email'),('04  Agent contribution','Gather evidence for the analyst to inspect')]):
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
   box(d,(65,275,725,458),'Sources you can inspect','Scoped tools gather the context.\nCitations connect you to the evidence.')
   box(d,(770,275,1475,458),'A next step you can act on','Reason  •  Missing context  •  Next action\nSaved with the evidence packet')
   drawtext(d,(65,540),'SecOps Triage',53,INK,True)
   drawtext(d,(65,622),'github.com/ArielSmoliar/secops-triage',34,TEAL)
   drawtext(d,(65,699),'Built with Strands Agents SDK  /  Agents for Humans',25,MUTED)
  im.save(out/(id+'.png'))
 if args.spotlight:
  def photo(im,name,area):
   src=Image.open(args.spotlight/(name+'.png')).convert('RGB');x,y,w,h=area;factor=min(w/src.width,h/src.height);size=(round(src.width*factor),round(src.height*factor));src=src.resize(size,Image.Resampling.LANCZOS);im.paste(src,(x+(w-size[0])//2,y))
  for sid in ('03-trace','04-messages','05-evidence','06-handoff'):
   im=Image.new('RGB',(1536,780),BG);d=ImageDraw.Draw(im)
   drawtext(d,(40,20),'SAVED EVIDENCE VIEW  /  MAGNIFIED FROM THE RECORDED RUN',19,TEAL,True)
   if sid=='03-trace':
    drawtext(d,(40,67),'One investigation. Nine inspectable evidence reads.',40,INK,True)
    photo(im,'trace',(40,140,1456,470))
    box(d,(40,610,755,750),'Agent contribution','Gather incident, entity, activity and case context.')
    box(d,(780,610,1496,750),'Analyst value','Inspect the sources in one evidence packet.')
   elif sid=='04-messages':
    drawtext(d,(40,67),'FIRST MESSAGE: APPROVED TRAINING',29,TEAL,True)
    drawtext(d,(790,67),'FOLLOW-UP: SUSPICIOUS LINK',29,'#efca85',True)
    photo(im,'message-training-detail',(40,120,700,590))
    photo(im,'message-followup-detail',(790,120,700,590))
    drawtext(d,(40,727),'The approval names the first message. It does not cover the follow-up.',31,INK,True)
   elif sid=='05-evidence':
    drawtext(d,(40,76),'Why investigate?',46,INK,True)
    drawtext(d,(40,174),'01  Exact link match',31,TEAL,True)
    drawtext(d,(40,223),'The retrieved intelligence\nidentifies this follow-up URL.',27,MUTED)
    drawtext(d,(40,341),'02  Source verdict',31,TEAL,True)
    drawtext(d,(40,390),'Synthetic provider: malicious',27,MUTED)
    drawtext(d,(40,483),'03  Reviewable next step',31,TEAL,True)
    drawtext(d,(40,532),'Host policy: investigate.\nCredential theft is unproven.',27,MUTED)
    drawtext(d,(595,81),'SOURCE: intelligence-exact-followup',25,TEAL,True)
    photo(im,'intelligence-detail',(590,137,900,594))
   else:
    drawtext(d,(40,77),'The next check is clear.',43,INK,True)
    drawtext(d,(40,180),'Request an authorized\nidentity audit export.',36,TEAL,True)
    drawtext(d,(40,319),'Inspect the exact\nfollow-up link.',36,TEAL,True)
    drawtext(d,(40,481),'Saved with the reason,\nmissing context and\nevidence packet.',31,MUTED)
    drawtext(d,(720,80),'ACTUAL SAVED HANDOFF',26,TEAL,True)
    photo(im,'handoff',(720,138,766,580))
   im.save(out/(sid+'-focus.png'))
if __name__=='__main__':main()
