"""Print-ready A4 award, with embedded Cyrillic fonts and a real verification QR."""
from datetime import timezone
from io import BytesIO
import math
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROMAN={1:'I',2:'II',3:'III'}
ACCENTS={1:'#B99A54',2:'#91A3B6',3:'#BA8367'}
_font_lock=Lock()

def register_fonts():
    with _font_lock:
        folder=Path(__file__).parent/'assets'/'fonts'
        for name,file in [('HFSans','DejaVuSans.ttf'),('HFBold','DejaVuSans-Bold.ttf'),('HFSerif','DejaVuSerif.ttf')]:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name,str(folder/file)))

def wrapped(text,font,size,width):
    lines=[];line=''
    for word in text.split():
        if line and pdfmetrics.stringWidth(line+' '+word,font,size)<=width:
            line+=' '+word
            continue
        if line:lines.append(line);line=''
        for char in word:
            candidate=line+char
            if pdfmetrics.stringWidth(candidate,font,size)>width and line:
                lines.append(line);line=''
            line+=char
    if line.strip():lines.append(line.strip())
    return [line.strip() for line in lines]

def text_block(c,text,x,y,width,font='HFSans',size=13,max_lines=2,min_size=9):
    lines=wrapped(text,font,size,width)
    while len(lines)>max_lines and size>min_size:
        size-=.5;lines=wrapped(text,font,size,width)
    c.setFont(font,size)
    for index,line in enumerate(lines):c.drawString(x,y-index*size*1.3,line)
    return y-(len(lines)-1)*size*1.3

def tracked(c,text,x,y,size=9,spacing=1.6,color='#687178'):
    c.saveState()
    c.setFillColor(HexColor(color));obj=c.beginText(x,y);obj.setFont('HFSans',size);obj.setCharSpace(spacing);obj.textOut(text);c.drawText(obj)
    c.restoreState()

def wreath(c,cx,cy,color):
    c.setStrokeColor(HexColor(color));c.setFillColor(HexColor(color));c.setLineWidth(.7)
    for direction in (-1,1):
        path=c.beginPath();path.moveTo(cx+direction*18,cy-65)
        path.curveTo(cx+direction*77,cy-43,cx+direction*82,cy+24,cx+direction*37,cy+66)
        c.drawPath(path)
        for i in range(8):
            angle=(-65+i*17)*math.pi/180
            x=cx+direction*(62*math.cos(angle));y=cy+62*math.sin(angle)
            c.saveState();c.translate(x,y);c.rotate(direction*(-25+i*13));c.ellipse(-2.3,-6,2.3,6,stroke=0,fill=1);c.restoreState()

def certificate_pdf(cert,verify_url):
    register_fonts();buffer=BytesIO();width,height=landscape(A4)
    c=Canvas(buffer,pagesize=(width,height),pageCompression=1)
    c.setTitle(f'Диплом · {cert.recipient_name} · {cert.event_title}')
    c.setAuthor('HackFlow');c.setCreator('HackFlow')
    ink='#223040';muted='#6E777C';paper='#FBFAF6';accent=ACCENTS[cert.place]
    c.setFillColor(HexColor(paper));c.rect(0,0,width,height,stroke=0,fill=1)
    c.setFillColor(HexColor(ink));c.rect(0,0,184,height,stroke=0,fill=1)
    c.setStrokeColor(HexColor('#304052'));c.setLineWidth(.7)
    for radius in (98,123,148):c.circle(10,68,radius,stroke=1,fill=0)
    c.setStrokeColor(HexColor(accent));c.setLineWidth(.7);c.rect(13,13,width-26,height-26,stroke=1,fill=0)
    c.setFillColor(HexColor('#F4EEDA'));c.setFont('HFBold',19);c.drawString(35,height-57,'hackflow')
    tracked(c,'ДОСТИЖЕНИЯ',36,height-78,7,1.6,'#A9B6BD')
    wreath(c,92,332,accent)
    c.setStrokeColor(HexColor(accent));c.setLineWidth(.4);c.circle(92,332,51,stroke=1,fill=0)
    c.setFont('HFSerif',62);c.setFillColor(HexColor('#F4EEDA'));c.drawCentredString(92,313,ROMAN[cert.place])
    tracked(c,'МЕСТО',68,245,9,2.2,'#D8CCAD')
    c.setFillColor(HexColor('#D4DFE3'));c.setFont('HFSans',7.5);c.drawString(35,105,'ДИПЛОМ №')
    c.setFont('HFBold',11);c.drawString(35,87,f'HF-{cert.id:06d}')
    issued=cert.issued_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Yekaterinburg'))
    c.setFont('HFSans',8);c.drawString(35,55,issued.strftime('%d.%m.%Y'))
    x=224;body_width=width-x-48
    c.setFillColor(HexColor(ink));c.setFont('HFSerif',38);c.drawString(x,490,'Диплом')
    tracked(c,'ПОБЕДИТЕЛЯ ХАКАТОНА',x,466,8.5,1.8,muted)
    c.setStrokeColor(HexColor(accent));c.setLineWidth(2);c.line(x,447,x+62,447)
    if cert.is_demo:
        tracked(c,'ДЕМО',width-95,524,8,1.3,muted)
    tracked(c,'НАГРАЖДАЕТСЯ',x,417,8,1.4,muted)
    c.setFillColor(HexColor(ink));text_block(c,cert.recipient_name,x,382,body_width,'HFSerif',30,2,18)
    c.setFillColor(HexColor(muted));c.setFont('HFSans',12);c.drawString(x,307,f'за {ROMAN[cert.place]} место в хакатоне')
    c.setFillColor(HexColor(ink));bottom=text_block(c,cert.event_title,x,276,body_width,'HFBold',21,3,13)
    c.setFillColor(HexColor(muted));text_block(c,'В составе команды «'+cert.team_name+'»',x,bottom-29,body_width,'HFSans',12,2,9)
    c.setStrokeColor(HexColor('#DBDDD8'));c.setLineWidth(.5);c.line(x,151,width-48,151)
    tracked(c,'ОРГАНИЗАТОР',x,128,7,1.2,muted)
    c.setFillColor(HexColor(ink));text_block(c,cert.organizer_name,x,108,body_width-100,'HFSans',11,2,8)
    c.setFillColor(HexColor(muted));c.setFont('HFSans',7);c.drawString(x,52,'Сформировано платформой HackFlow')
    qr=QrCodeWidget(verify_url,barLevel='M',barBorder=4,barFillColor=HexColor(ink))
    left,bottom,right,top=qr.getBounds();size=83
    drawing=Drawing(size,size,transform=[size/(right-left),0,0,size/(top-bottom),-left*size/(right-left),-bottom*size/(top-bottom)])
    drawing.add(qr);renderPDF.draw(drawing,c,width-132,55)
    c.setFont('HFSans',6.5);c.drawCentredString(width-90.5,43,'Проверить диплом')
    c.showPage();c.save();return buffer.getvalue()
