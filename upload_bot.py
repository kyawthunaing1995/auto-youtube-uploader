import os
import io
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# configuration သတ်မှတ်ချက်များ
DRIVE_FOLDER_ID = '1mU6CFCAU3caRayvn1DjV32V7SlyThlo1'
UPLOADED_LOG_FILE = 'uploaded.txt'

def get_authenticated_services():
    """GitHub Secrets ထဲက ပြန်လည်ရယူထားတဲ့ Environment Variable ကနေ Credentials ကို ဖတ်ပြီး
    Google Drive နဲ့ YouTube API Client များကို ဆောက်ပေးသည်"""
    creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json_str:
        raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable မတွေ့ရှိပါ။ GitHub Secrets တွင် သေချာထည့်သွင်းပေးပါ။")
        
    creds_info = json.loads(creds_json_str)
    creds = Credentials.from_authorized_user_info(creds_info)
    
    # Token သက်တမ်းကုန်နေပါက Refresh လုပ်မည်
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        
    drive_service = build('drive', 'v3', credentials=creds)
    youtube_service = build('youtube', 'v3', credentials=creds)
    
    return drive_service, youtube_service

def get_uploaded_videos():
    """တင်ပြီးသား ဗီဒီယိုစာရင်းကို uploaded.txt ကနေ ဖတ်ယူသည်"""
    if not os.path.exists(UPLOADED_LOG_FILE):
        return set()
    with open(UPLOADED_LOG_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def mark_as_uploaded(video_name):
    """ဗီဒီယိုအသစ်ကို တင်ပြီးကြောင်း uploaded.txt ထဲတွင် မှတ်သားသည်"""
    with open(UPLOADED_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(video_name + '\n')

def main():
    try:
        print("Bot စတင်အလုပ်လုပ်နေပြီ...")
        drive_service, youtube_service = get_authenticated_services()
        uploaded_videos = get_uploaded_videos()
        
        # ၁။ Google Drive Folder ထဲရှိ ဗီဒီယိုများကို ရှာဖွေခြင်း (အမည်အလိုက် စီမည်)
        query = f"'{DRIVE_FOLDER_ID}' in parents and mimeType startswith 'video/' and trashed = false"
        results = drive_service.files().list(
            q=query, 
            fields="files(id, name)",
            orderBy="name"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            print("သတ်မှတ်ထားသော Google Drive Folder ထဲတွင် ဗီဒီယိုမတွေ့ရှိပါ။")
            return
            
        # ၂။ တင်မရသေးသော ပထမဆုံးဗီဒီယိုကို ရွေးချယ်ခြင်း
        target_video = None
        for file in files:
            if file['name'] not in uploaded_videos:
                target_video = file
                break
                
        if not target_video:
            print("ဗီဒီယိုအားလုံးကို YouTube ပေါ် တင်ပြီးသွားပါပြီ။ တင်စရာအသစ် မရှိတော့ပါ။")
            return
            
        video_id = target_video['id']
        video_name = target_video['name']
        print(f"ယနေ့တင်ရန် ရွေးချယ်လိုက်သော ဗီဒီယို - {video_name}")
        
        # ၃။ ရွေးချယ်လိုက်သော ဗီဒီယိုကို GitHub Actions Runner ဆီသို့ ဒေါင်းလုဒ်ဆွဲခြင်း
        request = drive_service.files().get_media(fileId=video_id)
        local_filename = video_name
        
        print("Google Drive မှ ဗီဒီယို ဒေါင်းလုဒ်ဆွဲနေသည်...")
        with open(local_filename, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request, chunksize=1024*1024*10) # 10MB chunk
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"ဒေါင်းလုဒ်ဆွဲမှုနှုန်း: {int(status.progress() * 100)}%")
                
        print("ဒေါင်းလုဒ်ဆွဲခြင်း အောင်မြင်ပါသည်။")
        
        # ၄။ YouTube သို့ တင်ခြင်း
        # ဗီဒီယိုခေါင်းစဉ်အဖြစ် ဖိုင်နာမည်ထဲက .mp4 စတာတွေကို ဖယ်ထုတ်ပေးမည်
        title = os.path.splitext(video_name)[0]
        
        body = {
            'snippet': {
                'title': title,
                'description': f'{title} - Automatically uploaded via GitHub Actions.',
                'tags': ['automation', 'python', 'drive_to_youtube'],
                'categoryId': '22' # 22 သည် People & Blogs အတွက်ဖြစ်သည်
            },
            'status': {
                'privacyStatus': 'private' # အစပိုင်းတွင် Private အဖြစ်ပဲ တင်ထားမည် (Public ပြောင်းလိုက ပြောင်းနိုင်သည်)
            }
        }
        
        media = MediaFileUpload(
            local_filename, 
            mimetype='application/octet-stream', 
            resumable=True
        )
        
        print("YouTube ပေါ်သို့ ဗီဒီယို စတင် Upload တင်နေသည်...")
        request = youtube_service.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"YouTube Upload တင်မှုနှုန်း: {int(status.progress() * 100)}%")
                
        print(f"YouTube ပေါ်သို့ ဗီဒီယို တင်ခြင်း အောင်မြင်ပါသည်။ Video ID: {response['id']}")
        
        # ၅။ တင်ပြီးသားစာရင်းထဲသို့ ထည့်သွင်းခြင်း
        mark_as_uploaded(video_name)
        print(f"uploaded.txt ထဲတွင် {video_name} ကို မှတ်သားပြီးစီးပါပြီ။")
        
        # လိုအပ်ပါက ဒေါင်းလုဒ်ဆွဲထားသော ယာယီဗီဒီယိုဖိုင်ကို ပြန်ဖျက်မည်
        if os.path.exists(local_filename):
            os.remove(local_filename)
            
    except Exception as e:
        print(f"အမှားအယွင်း ဖြစ်ပွားခဲ့သည်: {e}")

if __name__ == '__main__':
    main()
