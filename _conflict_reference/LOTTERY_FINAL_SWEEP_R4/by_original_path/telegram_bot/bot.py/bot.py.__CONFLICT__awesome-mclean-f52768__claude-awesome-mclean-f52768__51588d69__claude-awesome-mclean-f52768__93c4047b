import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from openai import OpenAI

# ── Load Environment ───────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# 設定路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_PATHS = [
    os.path.join(BASE_DIR, "data", "wbc_backend", "reports", "latest", "last_report.txt"),
    os.path.join(BASE_DIR, "last_report.txt"),  # legacy fallback
]

# 設定日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 初始化 GitHub Models 客戶端 (免費 LLM API)
client = None
if GITHUB_TOKEN:
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=GITHUB_TOKEN,
    )

# ── Utilities ────────────────────────────────────────────────────────────

def get_latest_report_content():
    """讀取最新的報告內容作為 AI 的背景知識。"""
    for report_path in REPORT_PATHS:
        if os.path.exists(report_path):
            try:
                with open(report_path, "r") as f:
                    return f.read()[:5000] # 限制長度避免 Context 炸掉
            except Exception:
                continue
    return "查無報告數據。"

# ── Handlers ─────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /start 指令。"""
    user_id = str(update.effective_user.id)
    logging.info(f"收到來自 {user_id} 的 /start 指令")
    
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        await update.message.reply_text(
            f"🚫 **存取拒絕**\n\n你的 User ID 是 `{user_id}`\n\n請在 `.env` 中設定權限。",
            parse_mode='Markdown'
        )
        return

    welcome_text = (
        "🦞 **WBC Betting Bot 升級版 (AI Inside)**\n\n"
        "我現在已經具備了 **GPT 大腦**！你可以直接問我：\n"
        "• 「為什麼韓國勝率高？」\n"
        "• 「總分大於 7.5 的機率是多少？」\n"
        "• 「分析一下澳洲的優勢」\n\n"
        "🎯 /predict - 完整分析報告\n"
        "💰 /ev - 今日價值注單\n"
        "❓ /help - 說明"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **指令說明**\n\n"
        "• `/start` - 啟動機器人\n"
        "• `/predict` - 讀取最新分析報告\n"
        "• `/ev` - 今日 EV+ 投注建議\n\n"
        "💡 **直接對話**：你可以直接輸入任何關於 WBC 預測的問題，我會根據最新模型數據回答你。"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查詢預測結果。"""
    report_path = next((p for p in REPORT_PATHS if os.path.exists(p)), None)
    if report_path is None:
        await update.message.reply_text("📭 目前還沒有產出報告。")
        return

    try:
        with open(report_path, "r") as f:
            content = f.read()
            summary = content[:3800] 
            header = "📈 **最新分析報告**：\n\n---\n"
            try:
                await update.message.reply_text(f"{header}{summary}", parse_mode='Markdown')
            except:
                await update.message.reply_text(f"📈 最新分析報告 (純文字版)：\n\n---\n{summary}")
    except Exception as e:
        await update.message.reply_text(f"❌ 讀取報告錯誤: {str(e)}")

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """使用 LLM 處理用戶的提問。"""
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        return

    user_query = update.message.text
    logging.info(f"AI Chat: {user_id} asks '{user_query}'")

    if not client:
        await update.message.reply_text("🤖 我現在還沒有大腦 (未設定 GITHUB_TOKEN)，請聯絡管理員。")
        return

    # 傳送「思考中」的視覺效果
    temp_msg = await update.message.reply_text("⚡️ 正在分析模型數據...", parse_mode='Markdown')

    try:
        context_data = get_latest_report_content()
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 WBC 專業棒球分析助理。以下是今日最新的量化模型分析報告，"
                        f"請根據這些數據回答用戶的問題：\n\n{context_data}\n\n"
                        "回答規範：\n"
                        "1. 語氣專業、自信但嚴謹。\n"
                        "2. 使用繁體中文。\n"
                        "3. 如果數據中沒有提到的資訊，請誠實告知。\n"
                        "4. 結尾可以給予適度的投注建議(帶免責聲明)。"
                    )
                },
                {"role": "user", "content": user_query}
            ],
            model="gpt-4o-mini",
            temperature=0.7,
        )
        
        ai_reply = response.choices[0].message.content
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=temp_msg.message_id,
            text=ai_reply,
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"LLM Error: {str(e)}")
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=temp_msg.message_id,
            text=f"❌ AI 思考時發生錯誤。 (Error: {str(e)[:50]}...)"
        )

# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not TOKEN:
        print("❌ 錯誤: 未設定 TELEGRAM_BOT_TOKEN")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        
        # 註冊指令
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("predict", predict))
        
        # 註冊 AI 對話處理器 (非指令的訊息都由 AI 回答)
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_chat))
        
        print("🚀 WBC AI Bot 正在運作中 (Model: GPT-4o-mini)...")
        app.run_polling()
