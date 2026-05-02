import logging,re,json,os
from datetime import datetime,timedelta
from collections import defaultdict
from telegram import Update
from telegram.ext import Application,MessageHandler,CommandHandler,filters,ContextTypes

BOT_TOKEN=os.environ.get("BOT_TOKEN","8366671856:AAGr_pTzjR9u4cecRs5QaHQOWxbBWjee1IU")
ADMIN_ID=1881481551
GROUP_ID=-1002903458713
DATA_FILE="/app/data.json"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",level=logging.INFO)
logger=logging.getLogger(__name__)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

def parse_message(text):
    lines=[l.strip() for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return None
    result={"sana":None,"mashina":None,"reyslar":[],"yonilgi":0}
    for line in lines[:4]:
        dm=re.search(r"(\d{1,2})[.,]\s*(\d{2})[.,]\s*(\d{4})",line)
        if dm and not result["sana"]:
            result["sana"]=f"{dm.group(3)}-{dm.group(2)}-{int(dm.group(1)):02d}"
        cm=re.search(r"\b(\d{3,4}[\s.]?[A-Za-z]{0,3})\b",line)
        if cm and not result["mashina"]:
            result["mashina"]=cm.group(1).strip().upper().replace(" ","")
    if not result["sana"] or not result["mashina"]:
        return None
    for line in lines[1:]:
        rm=re.search(r"(\d+)\s*[-]\s*[Rr][Ee][Ss]",line)
        if rm:
            count=int(rm.group(1))
            manzil=re.sub(r"\s*\d+\s*[-]\s*[Rr][Ee][Ss].*","",line).strip()
            result["reyslar"].append({"manzil":manzil,"soni":count})
        fm=re.search(r"\b(\d{1,2})\.(\d{3})\b",line)
        if fm:
            result["yonilgi"]+=int(fm.group(1))*1000+int(fm.group(2))
        else:
            fm2=re.search(r"\bpag\s+(\d{3,4})\b",line,re.IGNORECASE)
            if fm2:
                result["yonilgi"]+=int(fm2.group(1))
    return result if result["reyslar"] else None

def save_record(parsed):
    data=load_data()
    sana=parsed["sana"]
    mashina=parsed["mashina"]
    if sana not in data:
        data[sana]={}
    if mashina not in data[sana]:
        data[sana][mashina]={"reyslar":[],"yonilgi":0}
    data[sana][mashina]["reyslar"].extend(parsed["reyslar"])
    data[sana][mashina]["yonilgi"]+=parsed["yonilgi"]
    save_data(data)

def generate_report(days=7):
    data=load_data()
    today=datetime.now().date()
    start=today-timedelta(days=days)
    filtered={}
    for s,m in data.items():
        try:
            d=datetime.strptime(s,"%Y-%m-%d").date()
        except:
            continue
        if start<=d<=today:
            filtered[s]=m
    if not filtered:
        return "Bu davrda malumot topilmadi."
    summary=defaultdict(lambda:{"jami_reys":0,"yonilgi":0,"manzillar":defaultdict(int)})
    for s,mashinalar in filtered.items():
        for mashina,info in mashinalar.items():
            summary[mashina]["jami_reys"]+=sum(r["soni"] for r in info["reyslar"])
            summary[mashina]["yonilgi"]+=info["yonilgi"]
            for r in info["reyslar"]:
                summary[mashina]["manzillar"][r["manzil"]]+=r["soni"]
    davr="Haftalik" if days<=7 else "Oylik"
    today_obj=datetime.now().date()
    start_obj=today_obj-timedelta(days=days)
    lines=[f"HISOBOT: {davr}",f"Sana: {start_obj.strftime('%d.%m.%Y')} - {today_obj.strftime('%d.%m.%Y')}","="*30]
    jr=0
    jy=0
    for mashina,info in sorted(summary.items()):
        lines.append(f"\nMashina: {mashina}")
        lines.append(f"Jami reys: {info['jami_reys']} ta")
        if info["yonilgi"]>0:
            lines.append(f"Yonilgi: {info['yonilgi']} l")
        if info["manzillar"]:
            lines.append("Manzillar:")
            for manzil,son in sorted(info["manzillar"].items(),key=lambda x:-x[1]):
                lines.append(f"  {manzil}: {son} reys")
        jr+=info["jami_reys"]
        jy+=info["yonilgi"]
    lines.append("="*30)
    lines.append(f"JAMI REYS: {jr} ta")
    if jy>0:
        lines.append(f"JAMI YONILGI: {jy} l")
    return "\n".join(lines)

async def handle_message(update:Update,context:ContextTypes.DEFAULT_TYPE):
    msg=update.message
    if not msg or not msg.text:
        return
    chat_id=msg.chat_id
    if chat_id!=GROUP_ID and chat_id!=ADMIN_ID:
        return
    text=msg.text
    parsed=parse_message(text)
    if parsed:
        save_record(parsed)
        logger.info(f"Saqlandi: {parsed['sana']} | {parsed['mashina']}")
        if chat_id==ADMIN_ID:
            await msg.reply_text(f"Saqlandi!\nSana: {parsed['sana']}\nMashina: {parsed['mashina']}\nReyslar: {len(parsed['reyslar'])} ta")
    else:
        if chat_id==ADMIN_ID and not text.startswith("/"):
            await msg.reply_text("Format xato!\nNamuna:\n29.04.2026. 709NN\nAYRLIWKA ZASPKA 2-RES")

async def cmd_hisobot(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        await update.message.reply_text("Ruxsat yoq.")
        return
    args=context.args
    days=30 if args and args[0]=="30" else 7
    report=generate_report(days=days)
    await context.bot.send_message(chat_id=ADMIN_ID,text=report)

async def cmd_bugun(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    report=generate_report(days=1)
    await context.bot.send_message(chat_id=ADMIN_ID,text=report)

async def cmd_start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot ishga tushdi!\n\n/hisobot - haftalik\n/hisobot 30 - oylik\n/bugun - bugungi")

def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",cmd_start))
    app.add_handler(CommandHandler("hisobot",cmd_hisobot))
    app.add_handler(CommandHandler("bugun",cmd_bugun))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
