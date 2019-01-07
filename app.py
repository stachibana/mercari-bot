import os
from flask import Flask, request, abort, send_file, render_template
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    ImageMessage,
    FollowEvent,
    FlexSendMessage,
    BubbleContainer,
    TextMessage,
    TextSendMessage
)
from PIL import Image
import redis
import urllib.parse
import uuid
import datetime
from flask_bootstrap import Bootstrap

url = urllib.parse.urlparse(os.environ["REDIS_URL"])
pool = redis.ConnectionPool(host=url.hostname,
                            port=url.port,
                            db=url.path[1:],
                            password=url.password,
                            decode_responses=True)
r = redis.StrictRedis(connection_pool=pool)

app = Flask(__name__, static_folder='imgs')
bootstrap = Bootstrap(app)

line_bot_api = LineBotApi(os.environ.get('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('CHANNEL_SECRET'))

@app.route("/")
def show_inquiry():
    return render_template('index.html')

@app.route("/", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    if event.message.text == '機能リクエスト':
        json = {
          "type": "bubble",
          "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
              {
                "type": "text",
                "text": '以下のフォームから入力してください♪',
                "weight": "bold",
                "size": "md",
                "wrap": True
              }
            ]
          },
          "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
              {
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {
                  "type": "uri",
                  "label": "フォームを開く",
                  "uri": "line://app/1636610661-exPKww1a"
                }
              }
            ],
            "flex": 0
          }
        }
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="代替テキスト", contents=BubbleContainer.new_from_json_dict(json))
        )
        return

    if event.message.text.startswith('送信完了'):

        r.rpush('inquiry', event.message.text)

        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text='受け付けました♪'),
            ]
        )
        return


    reply_text = ''
    available_texts = ['専用', 'SALE', '送料込み', '新品', 'ほぼ新品']

    if event.message.text in available_texts:
        r.set(event.source.user_id, str(available_texts.index(event.message.text) + 1).zfill(2))
        # Rich menu
        richmenu_list = ['richmenu-4318d8c8dba62fc14de3fced2943e413',
                         'richmenu-a9026960e6262156dcfb46f9ba4be03f',
                         'richmenu-f327f9da90dda0fdffd31ffa04cda8f3',
                         'richmenu-68ae2dde8a306b2ac5d83fe607bc5c45',
                         'richmenu-5ce596509156820b2661d67cf3ca8cd0',
                         ]
        line_bot_api.link_rich_menu_to_user(event.source.user_id, richmenu_list[available_texts.index(event.message.text)])

        json = {
          "type": "bubble",
          "hero": {
            "type": "image",
            "url": request.url_root.replace('http://', 'https://') + '/imgs/mercari_%s.png' % (r.get(event.source.user_id)),
            "size": "full",
            "aspectRatio": "1:1",
            "aspectMode": "cover"
          },
          "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
              {
                "type": "text",
                "text": '「' + event.message.text + '」に変更したよ。画像を送ってね♪',
                "weight": "bold",
                "size": "md",
                "wrap": True
              }
            ]
          },
          "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
              {
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {
                  "type": "uri",
                  "label": "画像を選択",
                  "uri": "line://nv/cameraRoll/multi"
                }
              }
            ],
            "flex": 0
          }
        }
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="代替テキスト", contents=BubbleContainer.new_from_json_dict(json))
        )
    else:
        reply_text = '載せたいテキストを変更したい時には↓をタップしてね。今は「' + available_texts[int(r.get(event.source.user_id)) - 1] + '」に設定されてるよ♪'

        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text=reply_text),
            ]
        )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):

    message_content = line_bot_api.get_message_content(event.message.id)
    dirname = 'imgs/tmp/' + datetime.date.today().strftime("%Y%m%d")
    filename = uuid.uuid4().hex
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open("%s/%s.jpg" % (dirname, filename), 'wb') as img:
        img.write(message_content.content)

    image_base = Image.open("%s/%s.jpg" % (dirname, filename))

    image_overlay = Image.open('imgs/mercari_%s.png' % (r.get(event.source.user_id)))

    if image_base.width >= 1000 and image_base.height >= 1000:
        image_base.thumbnail((1000, 1000))
    else:
        image_overlay.thumbnail(image_base.size)

    image_base.paste(image_overlay, (0, image_base.height - image_overlay.height), image_overlay)
    image_base.save("%s/%s_overlay.jpg" % (dirname, filename), quality=100)

    json = {
      "type": "bubble",
      "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": '加工完了♪',
            "weight": "bold",
            "size": "md",
            "wrap": True
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
              "type": "uri",
              "label": "ダウンロード",
              "uri": request.url_root.replace('http://', 'https://') + "/%s/%s_overlay.jpg" % (dirname, filename)
            }
          }
        ],
        "flex": 0
      }
    }
    line_bot_api.reply_message(
        event.reply_token,
        [
            FlexSendMessage(alt_text="代替テキスト", contents=BubbleContainer.new_from_json_dict(json))
        ]
    )

@handler.add(FollowEvent)
def handle_follow(event):
    r.set(event.source.user_id, '01')
    line_bot_api.link_rich_menu_to_user(event.source.user_id, 'richmenu-4318d8c8dba62fc14de3fced2943e413')

    json = {
      "type": "bubble",
      "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": "友達追加ありがとう！画像を送るとメルカリの出品用に「専用」「送料込み」等のテキストを追加するBotだよ。気に入ったら友達にもオススメしてね！'",
            "weight": "bold",
            "size": "md",
            "wrap": True
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
              "type": "uri",
              "label": "画像を選択",
              "uri": 'line://nv/cameraRoll/multi'
            }
          }
        ],
        "flex": 0
      }
    }
    line_bot_api.reply_message(
        event.reply_token,
        [
            FlexSendMessage(alt_text="代替テキスト", contents=BubbleContainer.new_from_json_dict(json))
        ]
    )

    line_bot_api.reply_message(
        event.reply_token,
        [
            TextSendMessage(text='友達追加ありがとう！画像を送るとメルカリの出品用に「専用」「送料込み」等のテキストを追加するBotだよ。気に入ったら友達にもオススメしてね！'),
        ]
    )

if __name__ == "__main__":
    app.debug = True
    app.run()
