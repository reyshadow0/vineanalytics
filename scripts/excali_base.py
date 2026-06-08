"""Primitivos compartidos para todos los generadores Excalidraw."""
import json, random, os

OUT = os.path.join(os.path.dirname(__file__), "..", "diagramas")
os.makedirs(OUT, exist_ok=True)

WINE="#8B1A1A"; WINE_D="#5C0E0E"; GOLD="#C9A84C"
GREEN="#2a6a10"; BLUE="#1a4a8a"; GRAY="#555555"; PURPLE="#6a1a8a"
WINE_L="#ffeaea"; GOLD_L="#fff8e8"; GREEN_L="#eafaee"
BLUE_L="#e8f0ff"; GRAY_L="#f5f5f5"; PURPLE_L="#f5e8ff"

def uid(): return "".join(random.choice("0123456789abcdef") for _ in range(20))
def s(): return random.randint(1000000,9999999)

def _b(t,x,y,w,h,stroke,bg,fill,sw,ss,rounded):
    return {"type":t,"id":uid(),"x":x,"y":y,"width":w,"height":h,
            "angle":0,"strokeColor":stroke,"backgroundColor":bg,
            "fillStyle":fill,"strokeWidth":sw,"strokeStyle":ss,
            "roughness":0,"opacity":100,"groupIds":[],"frameId":None,
            "roundness":{"type":3} if rounded else None,
            "seed":s(),"version":1,"versionNonce":s(),"isDeleted":False,
            "boundElements":[],"updated":1700000000000,"link":None,"locked":False}

def rect(x,y,w,h,bg="transparent",stroke="#1e1e1e",sw=2,ss="solid",rounded=True):
    return _b("rectangle",x,y,w,h,stroke,bg,"solid",sw,ss,rounded)

def diamond(x,y,w,h,bg="transparent",stroke="#1e1e1e",sw=2):
    e=_b("diamond",x,y,w,h,stroke,bg,"solid",sw,"solid",False)
    e["roundness"]=None; return e

def ell(x,y,w,h,bg="transparent",stroke="#1e1e1e",sw=2):
    e=_b("ellipse",x,y,w,h,stroke,bg,"solid",sw,"solid",False)
    e["roundness"]={"type":2}; return e

def line(x1,y1,x2,y2,stroke="#1e1e1e",sw=2,ss="solid"):
    e=_b("line",x1,y1,abs(x2-x1)+1,abs(y2-y1)+1,stroke,"transparent","solid",sw,ss,False)
    e["roundness"]={"type":2}
    e["points"]=[[0,0],[x2-x1,y2-y1]]
    e["lastCommittedPoint"]=None
    e["startBinding"]=None; e["endBinding"]=None
    e["startArrowhead"]=None; e["endArrowhead"]=None
    return e

def arr(x1,y1,x2,y2,stroke="#8B1A1A",sw=2,ss="solid",sh=None,eh="arrow"):
    e=_b("arrow",x1,y1,abs(x2-x1)+1,abs(y2-y1)+1,stroke,"transparent","solid",sw,ss,False)
    e["roundness"]={"type":2}
    e["points"]=[[0,0],[x2-x1,y2-y1]]
    e["lastCommittedPoint"]=None
    e["startBinding"]=None; e["endBinding"]=None
    e["startArrowhead"]=sh; e["endArrowhead"]=eh
    return e

def txt(t,x,y,size=13,color="#1e1e1e",align="left",font=2):
    w=max(len(t)*size*0.58,30)
    return {"type":"text","id":uid(),"x":x,"y":y,"width":w,"height":size*1.4,
            "angle":0,"strokeColor":color,"backgroundColor":"transparent",
            "fillStyle":"solid","strokeWidth":1,"strokeStyle":"solid",
            "roughness":0,"opacity":100,"groupIds":[],"frameId":None,
            "roundness":None,"seed":s(),"version":1,"versionNonce":s(),
            "isDeleted":False,"boundElements":[],"updated":1700000000000,
            "link":None,"locked":False,
            "text":t,"fontSize":size,"fontFamily":font,
            "textAlign":align,"verticalAlign":"top",
            "containerId":None,"originalText":t,"lineHeight":1.25}

def title(t,x,y,sub=""):
    els=[txt(t,x,y,size=20,color=WINE_D,align="center")]
    if sub: els.append(txt(sub,x,y+26,size=12,color=GRAY,align="center"))
    return els

def save(name,elements,bg="#ffffff"):
    data={"type":"excalidraw","version":2,"source":"https://excalidraw.com",
          "elements":elements,
          "appState":{"gridSize":None,"viewBackgroundColor":bg},"files":{}}
    with open(os.path.join(OUT,name),"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2,ensure_ascii=False)
    print(f"  OK  {name}")

# ── composite helpers ───────────────────────────────────────────────────────
def stick(cx,cy,label,color="#333",size=12):
    return [ell(cx-13,cy-26,26,26,stroke=color,sw=2),
            line(cx,cy,cx,cy+44,stroke=color,sw=2),
            line(cx-22,cy+16,cx+22,cy+16,stroke=color,sw=2),
            line(cx,cy+44,cx-18,cy+72,stroke=color,sw=2),
            line(cx,cy+44,cx+18,cy+72,stroke=color,sw=2),
            txt(label,cx-55,cy+76,size=size,color=color,align="center")]

def uc_oval(label,x,y,fill=WINE_L,stroke=WINE,size=12):
    w=max(len(label)*7+32,160); h=36
    return [ell(x-w//2,y-h//2,w,h,bg=fill,stroke=stroke,sw=2),
            txt(label,x-w//2+8,y-8,size=size,color=WINE_D,align="center")],(x,y)

def db_table(x,y,title_t,sub,pk,cols,hbg=BLUE,hfg="#fff",bbg="#f0f8ff",w=220):
    els=[]; rh=24; th=38; bh=rh*(len(cols)+1)+10
    # header
    els.append(rect(x,y,w,th,bg=hbg,stroke=hbg,sw=0,rounded=True))
    els.append(rect(x,y+th-10,w,12,bg=hbg,stroke=hbg,sw=0,rounded=False))
    els.append(txt(title_t,x+w//2,y+5,size=13,color=hfg,align="center"))
    els.append(txt(sub,x+w//2,y+20,size=9,color=f"{hfg}99",align="center"))
    # body
    els.append(rect(x,y+th,w,bh,bg=bbg,stroke=hbg,sw=2,rounded=False))
    # PK row
    els.append(rect(x+2,y+th+2,w-4,rh-2,bg="#fff8e8",stroke="none",sw=0,rounded=True))
    els.append(txt(f"PK  {pk[0]}",x+10,y+th+6,size=11,color="#8a6010"))
    els.append(txt(pk[1],x+w-75,y+th+6,size=10,color="#aaa"))
    els.append(line(x+2,y+th+rh,x+w-2,y+th+rh,stroke="#ddd",sw=1))
    for i,(c,dt) in enumerate(cols):
        ry=y+th+rh+i*rh
        if i%2==0: els.append(rect(x+2,ry+1,w-4,rh-2,bg="#f8faff",stroke="none",sw=0,rounded=False))
        prefix="FK  " if c.startswith("id_") else "    "
        col=f"{prefix}{c}"; color=GOLD if prefix.strip()=="FK" else "#333"
        els.append(txt(col,x+8,ry+6,size=11,color=color))
        els.append(txt(dt,x+w-75,ry+6,size=10,color="#aaa"))
    return els,x+w//2,y+th+bh//2

def activity(x,y,w,h,label,bg="#fff8f0",stroke=WINE):
    return [rect(x,y,w,h,bg=bg,stroke=stroke,sw=2,rounded=True),
            txt(label,x+8,y+h//2-8,size=12,color="#333")]

def decision(x,y,w,h,label,bg=GOLD_L,stroke=GOLD):
    cx=x+w//2; cy=y+h//2
    return [diamond(x,y,w,h,bg=bg,stroke=stroke,sw=2),
            txt(label,cx-len(label)*4,cy-8,size=11,color="#333",align="center")]

def start_node(x,y,r=14):
    e=ell(x-r,y-r,r*2,r*2,bg="#1e1e1e",stroke="#1e1e1e",sw=2)
    return [e]

def end_node(x,y,r=14):
    return [ell(x-r-4,y-r-4,(r+4)*2,(r+4)*2,stroke="#1e1e1e",sw=2),
            ell(x-r,y-r,r*2,r*2,bg="#1e1e1e",stroke="#1e1e1e",sw=2)]

def state_box(x,y,w,h,label,sublabel="",bg=BLUE_L,stroke=BLUE):
    els=[rect(x,y,w,h,bg=bg,stroke=stroke,sw=2,rounded=True),
         txt(label,x+w//2,y+8,size=13,color=stroke,align="center")]
    if sublabel: els.append(txt(sublabel,x+8,y+26,size=10,color=GRAY))
    return els

def swim_header(x,y,w,h,label,bg,stroke):
    return [rect(x,y,w,h,bg=bg,stroke=stroke,sw=2,rounded=True),
            txt(label,x+w//2,y+h//2-8,size=13,color=stroke,align="center")]

def note_box(x,y,w,h,text_content,bg="#fffde7",stroke="#f0c000"):
    return [rect(x,y,w,h,bg=bg,stroke=stroke,sw=1,ss="dashed",rounded=True),
            txt(text_content,x+8,y+8,size=11,color="#555")]

def lifeline(x,y0,y1,label,sub="",bg="#f0f0f0",stroke="#333"):
    return [rect(x-55,y0,110,40,bg=bg,stroke=stroke,sw=2,rounded=True),
            txt(label,x-45,y0+5,size=12,color=stroke,align="center"),
            txt(sub,x-45,y0+20,size=10,color=GRAY,align="center"),
            line(x,y0+40,x,y1,stroke=stroke,sw=1,ss="dashed")]

def msg(x1,x2,y,label,stroke="#333",dashed=False,sw=1,ret=False):
    a=arr(x1,y,x2,y,stroke=stroke,sw=sw,ss="dashed" if dashed or ret else "solid",
          sh="arrow" if ret else None, eh="arrow")
    mx=min(x1,x2)+abs(x2-x1)//2
    t=txt(label,mx-len(label)*4,y-16,size=10,color=stroke,align="center")
    return [a,t]

def seq_frame(x,y,w,h,label,color=GRAY):
    return [rect(x,y,w,h,stroke=color,sw=1,ss="dashed",rounded=False),
            rect(x,y,max(len(label)*7+8,60),18,bg=color,stroke=color,sw=0,rounded=False),
            txt(label,x+4,y+2,size=10,color="#fff")]

def component_box(x,y,w,h,label,sub="",bg=BLUE_L,stroke=BLUE):
    els=[rect(x,y,w,h,bg=bg,stroke=stroke,sw=2,rounded=True)]
    # component icon top-right
    ix,iy=x+w-28,y+8
    els.append(rect(ix,iy,20,14,bg="#fff",stroke=stroke,sw=1,rounded=False))
    els.append(rect(ix-5,iy+2,8,4,bg=stroke,stroke=stroke,sw=0,rounded=False))
    els.append(rect(ix-5,iy+8,8,4,bg=stroke,stroke=stroke,sw=0,rounded=False))
    els.append(txt(label,x+10,y+h//2-(10 if sub else 7),size=13,color=stroke))
    if sub: els.append(txt(sub,x+10,y+h//2+6,size=10,color=GRAY))
    return els
