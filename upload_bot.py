import os
import json
import base64
import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io

# === ၁။ သတ်မှတ်ချက်များ (Configurations) ===
DRIVE_FOLDER_ID = '1mU6CFCAU3caRayvn1DjV32V7SlyThlo1'  # သင့် Google Drive ဖိုဒါ ID အမှန်
UPLOAD_TRACK_FILE = 'uploaded.txt'
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/youtube.upload'
]

# === ၂။ အကူအညီပေးမည့် လုပ်ဆောင်ချက်များ (Helper Functions) ===
def get_uploaded_videos():
    if not os.path.exists(UPLOAD_TRACK_FILE):
        return set()
    with open(UPLOAD_TRACK_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def mark_as_uploaded(video_name):
    with open(UPLOAD_TRACK_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{video_name}\n")

# === ၃။ အဓိက လုပ်ဆောင်ချက် (Main Logic) ===
def main():
    print("Bot စတင်အလုပ်လုပ်နေပြီ...")
    
    creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json_str:
        print("အမှားအယွင်း: GOOGLE_CREDENTIALS_JSON လျှို့ဝှက်ချက် မရှိသေးပါ။")
        return
        
    creds_info = json.loads(creds_json_str)
    creds = google.oauth2.credentials.Credentials.from_authorized_user_info(creds_info, SCOPES)
    
    drive_service = build('drive', 'v3', credentials=creds)
    youtube_service = build('youtube', 'v3', credentials=creds)
    
    uploaded_list = get_uploaded_videos()
    
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
    
    print("Google Drive မှ ဗီဒီယို ဒေါင်းလုဒ်ဆွဲနေသည်...")
    request = drive_service.files().get_media(fileId=video_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"ဒေါင်းလုဒ်ဆွဲနှုန်း: {int(status.progress() * 100)}%")
    print("ဒေါင်းလုဒ်ဆွဲခြင်း အောင်မြင်ပါသည်။")
    
    fh.seek(0)
    video_title = os.path.splitext(video_name)[0].replace('_', ' ')
    
    body = {
        'snippet': {
            'title': video_title[:100],  
            'description': f"{video_title} - ကောင်းမူတခုနေ့စဉ်ပြုကြပါ ဓမ္မမိတ်ဆွေတို့",
            'tags': ['auto-upload', 'video'],
            'categoryId': '22'  
        },
        'status': {
            'privacyStatus': 'public'  
        }
    }
    
    # 🌟 ဖိုင်နာမည် ရောထွေးမှုမရှိအောင် temp_video.mp4 ဟု နာမည်အသေသတ်မှတ်ပြီး သိမ်းဆည်းခြင်း
    local_file_name = "temp_video.mp4"
    with open(local_file_name, 'wb') as local_file:
        local_file.write(fh.read())
        
    print("YouTube ပေါ်သို့ ဗီဒီယို စတင် Upload တင်နေသည်...")
    try:
        # 🌟 MediaFileUpload တွင် local_file_name ကို တိုက်ရိုက်အသုံးပြုရန် အသေပြင်ဆင်ထားပါသည်
        media = MediaFileUpload(local_file_name, mimetype='video/*', resumable=True)
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
        
        mark_as_uploaded(video_name)
        print(f"uploaded.txt ထဲတွင် {video_name} ကို မှတ်သားပြီးစီးပါပြီ။")
        
        try:
            drive_service.files().update(
                fileId=video_id,
                body={'trashed': True}
            ).execute()
            print(f"Google Drive ရှိ '{video_name}' ကို အမှိုက်ပုံးသို့ ရွှေ့ပြီးပါပြီ။")
        except Exception as trash_err:
            print(f"သတိပေးချက်: Drive ဖိုင်ကို အမှိုက်ပုံးသို့ မရွှေ့နိုင်ခဲ့ပါ: {trash_err}")
            
    except Exception as upload_err:
        print(f"YouTube သို့ တင်ရာတွင် အမှားပြနေပါသည်: {upload_err}")
        
    finally:
        # စက်ထဲရှိ ယာယီဖိုင်အား ပြန်လည်ဖျက်သိမ်းခြင်း
        if os.path.exists(local_file_name):
            os.remove(local_file_name)

if __name__ == '__main__':
    main()
