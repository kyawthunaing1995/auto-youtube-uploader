import os
import json
import base64
import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io

# === ၁။ သတ်မှတ်ချက်များ (Configurations) ===
DRIVE_FOLDER_ID = '1Z_yJ97R-D8e87N_YI7W_M9v7GZ9X_X7P'  # သင့် Google Drive ဖိုဒါ ID
UPLOAD_TRACK_FILE = 'uploaded.txt'

# 🌟 Scope ကို ReadOnly မှ ဖိုင်ပြင်ဆင်ခွင့်/ဖျက်ခွင့် (drive) ရရှိအောင် ပြောင်းလဲထားပါသည်
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/youtube.upload'
]

# === ၂။ အကူအညီပေးမည့် လုပ်ဆောင်ချက်များ (Helper Functions) ===
def get_uploaded_videos():
    """တင်ပြီးသား ဗီဒီယိုစာရင်းကို uploaded.txt မှ ဖတ်ယူခြင်း"""
    if not os.path.exists(UPLOAD_TRACK_FILE):
        return set()
    with open(UPLOAD_TRACK_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def mark_as_uploaded(video_name):
    """တင်ပြီးသွားသော ဗီဒီယိုကို uploaded.txt ထဲသို့ ထည့်သွင်းခြင်း"""
    with open(UPLOAD_TRACK_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{video_name}\n")

# === ၃။ အဓိက လုပ်ဆောင်ချက် (Main Logic) ===
def main():
    print("Bot စတင်အလုပ်လုပ်နေပြီ...")
    
    # GitHub Secrets မှတစ်ဆင့် Google Credentials JSON ကို ဖတ်ယူခြင်း
    creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json_str:
        print("အမှားအယွင်း: GOOGLE_CREDENTIALS_JSON လျှို့ဝှက်ချက် မရှိသေးပါ။")
        return
        
    creds_info = json.loads(creds_json_str)
    creds = google.oauth2.credentials.Credentials.from_authorized_user_info(creds_info, SCOPES)
    
    # Google API Services များ တည်ဆောက်ခြင်း
    drive_service = build('drive', 'v3', credentials=creds)
    youtube_service = build('youtube', 'v3', credentials=creds)
    
    # ယခင် တင်ဖူးပြီးသား ဗီဒီယိုများ စာရင်းကို ယူခြင်း
    uploaded_list = get_uploaded_videos()
    
    # Google Drive ဖိုဒါထဲမှ ဗီဒီယိုဖိုင်များကို ရှာဖွေခြင်း
    query = f"'{DRIVE_FOLDER_ID}' in parents and mimeType contains 'video/' and trashed = false"
    try:
        results = drive_service.files().list(
            q=query,
            fields="files(id, name)",
            orderBy="name"
        ).execute()
        files = results.get('files', [])
    except Exception as e:
        print(f"အမှားအယွင်း ဖြစ်ပွားခဲ့သည်: {e}")
        return

    if not files:
        print("သတ်မှတ်ထားသော Google Drive ဖိုဒါထဲတွင် ဗီဒီယိုမတွေ့ရှိပါ။")
        return
        
    # မတင်ရသေးသော ဗီဒီယိုအသစ်တစ်ပုဒ်ကို ရွေးချယ်ခြင်း
    target_file = None
    for f in files:
        if f['name'] not in uploaded_list:
            target_file = f
            break
            
    if not target_file:
        print("ဖိုဒါထဲရှိ ဗီဒီယိုအားလုံးကို တင်ပြီးသွားပါပြီ။ ဗီဒီယိုအသစ် မရှိပါ။")
        return
        
    video_id = target_file['id']
    video_name = target_file['name']
    print(f"ယနေ့တင်ရန် ရွေးချယ်လိုက်သော ဗီဒီယို - {video_name}")
    
    # ဗီဒီယိုအား စက်ထဲသို့ ဒေါင်းလုဒ်ဆွဲခြင်း
    print("Google Drive မှ ဗီဒီယို ဒေါင်းလုဒ်ဆွဲနေသည်...")
    request = drive_service.files().get_media(fileId=video_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"ဒေါင်းလုဒ်ဆွဲနှုန်း: {int(status.progress() * 100)}%")
    print("ဒေါင်းလုဒ်ဆွဲခြင်း အောင်မြင်ပါသည်။")
    
    # ဗီဒီယိုဖိုင်ကို ယူကျုပေါ်တင်ရန် ပြင်ဆင်ခြင်း
    fh.seek(0)
    # ဖိုင်အမည်မှ လိုင်းအောက်ကုတ် (_) များကို ဖျက်ပြီး ယူကျု Title အဖြစ် သုံးရန် ပြင်ခြင်း
    video_title = os.path.splitext(video_name)[0].replace('_', ' ')
    
    body = {
        'snippet': {
            'title': video_title[:100],  # YouTube Title မှာ စာလုံး ၁၀၀ အထိပဲ ခွင့်ပြုလို့ပါ
            'description': f"{video_title} - အလိုအလျောက် စနစ်ဖြင့် တင်ပေးထားသော ဗီဒီယို ဖြစ်ပါသည်။",
            'tags': ['auto-upload', 'video'],
            'categoryId': '22'  # People & Blogs ကဏ္ဍ
        },
        'status': {
            'privacyStatus': 'public'  # 🌟 Public အဖြစ် လူတိုင်းကြည့်ရှုနိုင်အောင် တင်ပေးမည်
        }
    }
    
    media = MediaFileUpload(
        video_name,  # နာမည်အတိုင်း သတ်မှတ်သည်
        mimetype='video/*',
        resumable=True
    )
    # BytesIO မှ လက်ရှိဖိုင်လမ်းကြောင်းသို့ ယာယီရေးသားခြင်း
    with open(video_name, 'wb') as local_file:
        local_file.write(fh.read())
        
    print("YouTube ပေါ်သို့ ဗီဒီယို စတင် Upload တင်နေသည်...")
    try:
        media = MediaFileUpload(video_name, mimetype='video/*', resumable=True)
        upload_request = youtube_service.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = upload_request.next_chunk()
            if status:
                print(f"YouTube သို့ တင်နေနှုန်း: {int(status.progress() * 100)}%")
                
        print(f"YouTube ပေါ်သို့ ဗီဒီယို တင်ခြင်း အောင်မြင်ပါသည်။ Video ID: {response['id']}")
        
        # ၅။ တင်ပြီးသားစာရင်းထဲသို့ ထည့်သွင်းခြင်း
        mark_as_uploaded(video_name)
        print(f"uploaded.txt ထဲတွင် {video_name} ကို မှတ်သားပြီးစီးပါပြီ။")
        
        # 🌟 ၆။ အလိုအလျောက် စနစ်သစ် - Google Drive မှ ဖိုင်ကို အမှိုက်ပုံး (Trash) သို့ ရွှေ့ခြင်း
        try:
            drive_service.files().update(
                fileId=video_id,
                body={'trashed': True}
            ).execute()
            print(f"ဂျာနယ်/ဗီဒီယို ပြီးဆုံးသဖြင့် Google Drive ရှိ '{video_name}' ကို အမှိုက်ပုံးသို့ ရွှေ့ပြီးပါပြီ။")
        except Exception as trash_err:
            print(f"သတိပေးချက်: Drive ဖိုင်ကို အမှိုက်ပုံးသို့ မရွှေ့နိုင်ခဲ့ပါ: {trash_err}")
            
    except Exception as upload_err:
        print(f"YouTube သို့ တင်ရာတွင် အမှားပြနေပါသည်: {upload_err}")
        
    finally:
        # ယာယီဒေါင်းလုဒ်ဆွဲထားသော ဗီဒီယိုဖိုင်အား စက်ထဲမှ ပြန်ဖျက်ခြင်း
        if os.path.exists(video_name):
            os.remove(video_name)

if __name__ == '__main__':
    main()
