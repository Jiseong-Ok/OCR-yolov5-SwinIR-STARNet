# -*- coding: utf-8 -*-
"""demo.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1MW_nbzBaoyoZYQ9p5B8DWQdFh34Z2s8S
"""

from PIL import Image
import cv2
import matplotlib.pyplot as plt
import numpy as np
import os
import gdown

import string
import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F

from swinir import SwinIR
from model import TPS_SpatialTransformerNetwork, LocalizationNetwork, GridGenerator, BasicBlock, ResNet, ResNet_FeatureExtractor, CTCLabelConverter, BidirectionalLSTM, Model, ResizeNormalize


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def sr(sr_model_path, image, scale = 4):

    if sr_model_path is None:
      
      url = "https://drive.google.com/uc?id=1d1RwNhiyxVu7zkNcIReifcyg5wkVc-xv"
      output = "003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x4_GAN.pth"

      if not os.path.exists('/content/OCR-yolov5-SwinIR-STARNet/'+output):
        
        sr_model_path = gdown.download(url, output, quiet=False)
      sr_model_path = '/content/OCR-yolov5-SwinIR-STARNet/'+output
      
        
    else:
      sr_model_path = sr_model_path

    img_lq = image.astype(np.float32) / 255.
    img_lq = np.transpose(img_lq if img_lq.shape[2] == 1 else img_lq[:, :, [2, 1, 0]], (2, 0, 1))  # HCW-BGR to CHW-RGB
    img_lq = torch.from_numpy(img_lq).float().unsqueeze(0).to(device)  # CHW-RGB to NCHW-RGB

    
    
    model = SwinIR(upscale=scale, in_chans=3, img_size=64, window_size=8,
                            img_range=1., depths=[6, 6, 6, 6, 6, 6, 6, 6, 6], embed_dim=240,
                            num_heads=[8, 8, 8, 8, 8, 8, 8, 8, 8],
                            mlp_ratio=2, upsampler='nearest+conv', resi_connection='3conv')
    param_key_g = 'params_ema'

    pretrained_model = torch.load(sr_model_path)
    model.load_state_dict(pretrained_model[param_key_g] if param_key_g in pretrained_model.keys() else pretrained_model, strict=True)

    model.eval()
    model = model.to(device)

    with torch.no_grad():
        # pad input image to be a multiple of window_size
        _, _, h_old, w_old = img_lq.size()
        h_pad = (h_old // window_size + 1) * window_size - h_old
        w_pad = (w_old // window_size + 1) * window_size - w_old
        img_lq = torch.cat([img_lq, torch.flip(img_lq, [2])], 2)[:, :, :h_old + h_pad, :]
        img_lq = torch.cat([img_lq, torch.flip(img_lq, [3])], 3)[:, :, :, :w_old + w_pad]
        output = model(img_lq)   # test로 예측한다 -> 살펴보기( ) -> tile이 None일때(기본값) 이렇게 예측
        output = output[..., :h_old * scale, :w_old * scale]

    # save image
    output = output.data.squeeze().float().cpu().clamp_(0, 1).numpy()
    if output.ndim == 3:
        output = np.transpose(output[[2, 1, 0], :, :], (1, 2, 0))  # CHW-RGB to HCW-BGR
    output = (output * 255.0).round().astype(np.uint8)  # float32 to uint8

    return output



def itt(itt_model_path, batch_max_length, batch_size, imgW, imgH, character, image):

    if itt_model_path is None:
      
      url = "https://drive.google.com/uc?id=1-YU62Q-yIap3yg6u7CCulP58fLS0QdZR"
      output = "best_norm_ED.pth"

      if not os.path.exists('/content/OCR-yolov5-SwinIR-STARNet/'+output):
        
        itt_model_path = gdown.download(url, output, quiet=False)
      itt_model_path = '/content/OCR-yolov5-SwinIR-STARNet/'+output
      
        
    else:
      itt_model_path = itt_model_path

    image=Image.fromarray(image)
    transform = ResizeNormalize((imgW, imgH)) #imgW, imgH 가 size라는 변수로 들어감
    image_tensors = transform(image)
    image_tensors = image_tensors.reshape(-1, 1, imgH, imgW)

    model = Model()
    model = torch.nn.DataParallel(model).to(device)

    model.load_state_dict(torch.load(itt_model_path, map_location=device))
    model.eval()

    converter = CTCLabelConverter(character)

    with torch.no_grad():
        image = image_tensors.to(device)
        text_for_pred = torch.LongTensor(batch_size, batch_max_length + 1).fill_(0).to(device)

        preds = model(image, text_for_pred)
        preds_size = torch.IntTensor([preds.size(1)] * batch_size)
        _, preds_index = preds.max(2)
        # preds_index = preds_index.view(-1)
        preds_str = converter.decode(preds_index, preds_size)   
    
    return preds_str



def yolov5s_detect(yolo_model_path, image) :
    # !gdown --id 10xmrzFfeRjVUWGS9onsuDkLrrRylrhLw
    # path = '/content/best.pt'
    # model = torch.hub.load('ultralytics/yolov5', 'custom', path=path)

    if yolo_model_path is None:
      
      url = "https://drive.google.com/uc?id=10xmrzFfeRjVUWGS9onsuDkLrrRylrhLw"
      output = "best.pt"

      if not os.path.exists('/content/OCR-yolov5-SwinIR-STARNet/'+output):
        
        yolo_model_path = gdown.download(url, output, quiet=False)
      yolo_model_path = '/content/OCR-yolov5-SwinIR-STARNet/'+output
      
    else:
      yolo_model_path = yolo_model_path

    model = torch.hub.load('ultralytics/yolov5', 'custom', path=yolo_model_path)


    data_img = image

    results = model(data_img)
    print('탐지된 이미지의 수 : ',len(results.xyxy[0]))
    
    crop_images = []
    for idx in range(len(results.xyxy[0])) :

        xy = results.xyxy[0][idx].cpu().numpy()

        start = (int(xy[1]),int(xy[0])) # y, x좌표 min값
        end = (int(xy[3]),int(xy[2])) # y, x좌표 max값

        output = np.zeros((end[0]-start[0], end[1]-start[1], 3), np.uint8)
        # print(output.shape)

        for y in range(output.shape[1]):
            for x in range(output.shape[0]):
                xp, yp = x + start[0], y+start[1]
                output[x,y] = image[xp,yp]

        # crop image
        crop_image = np.asarray(output)
 
        crop_images.append(crop_image)
  
        
    return crop_images, results.xyxy[0]



def img_blur_text(font_path, image, bboxs, texts, mag=30):
  
    if font_path is None:
      
      url = "https://drive.google.com/uc?id=17IK1YuODQxjJDQtVEqOF22EtvDh37wUs"
      output = "NanumBarunGothic.ttf"

      if not os.path.exists('/content/OCR-yolov5-SwinIR-STARNet/'+output):
        
        font_path = gdown.download(url, output, quiet=False)
      font_path = '/content/OCR-yolov5-SwinIR-STARNet/'+output
      
    else:
      font_path = font_path


    #   img = Image.open(image).convert('RGB')
    #   blurI = img.filter(ImageFilter.GaussianBlur(50))

    
    img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

  
    
    for bbox, text in zip(bboxs, texts):
        x = int(bbox[0])
        y = int(bbox[1])
        x_ = int(bbox[2])
        y_ = int(bbox[3])

        roi = img[y:y_, x:x_]
        roi = cv2.blur(roi, (mag, mag))
        img[y:y_, x:x_] = roi

        img_p = Image.fromarray(img)

        text_size = int((bbox[3]-bbox[1])*0.9)

        # 글자 위치
        xs, ys = int(x*1.02), int(y*1.02)
        text_pos = (xs, ys)

        # 글자 타입 ( 글자 폰트, 글자 크기)
        font_type = ImageFont.truetype(font_path, text_size)
    
        # 글자색
        color = (0,0,0)

        draw = ImageDraw.Draw(img_p)

        draw.text(text_pos, text[0], color, font=font_type)
        
        img = np.array(img_p) 
        # 텍스트가 쓰여진 이미지를 다시 배열로 바꿔서 for문을 돌 수 있게 사용

    return img

def demo(opt):

    img = cv2.imread(opt.image_path)
    crop_images, bboxs = yolov5s_detect(opt.yolo_model_path, image = img)

    texts = []
    for crop_image in crop_images:
        sr_img = sr(opt.sr_model_path, image = crop_image)
        text = itt(opt.itt_model_path, opt.batch_max_length, opt.batch_size, opt.imgW, opt.imgH, opt.character, image = sr_img)
        texts.append(text)

    img_t = img_blur_text(opt.font_path, image=img, bboxs=bboxs, texts=texts)

    plt.imshow(img_t)
    plt.show()



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_path', required=True, help='path to image which contains text images')
    parser.add_argument('--workers', type=int, help='number of data loading workers', default=4)
    parser.add_argument('--batch_size', type=int, default=1, help='input batch size')
    """ Data processing """
    parser.add_argument('--batch_max_length', type=int, default=25, help='maximum-label-length')
    parser.add_argument('--imgH', type=int, default=64, help='the height of the input image')
    parser.add_argument('--imgW', type=int, default=200, help='the width of the input image')
    parser.add_argument('--rgb', action='store_true', help='use rgb input')
    parser.add_argument('--character', type=str, default='0123456789abcdefghijklmnopqrstuvwxyz가각간갇갈감갑값갓강갖같갚갛개객걀걔거걱건걷걸검겁것겉게겨격겪견결겹경곁계고곡곤곧골곰곱곳공과관광괜괴굉교구국군굳굴굵굶굽궁권귀귓규균귤그극근글긁금급긋긍기긴길김깅깊까깍깎깐깔깜깝깡깥깨꺼꺾껌껍껏껑께껴꼬꼭꼴꼼꼽꽂꽃꽉꽤꾸꾼꿀꿈뀌끄끈끊끌끓끔끗끝끼낌나낙낚난날낡남납낫낭낮낯낱낳내냄냇냉냐냥너넉넌널넓넘넣네넥넷녀녁년념녕노녹논놀놈농높놓놔뇌뇨누눈눕뉘뉴늄느늑는늘늙능늦늬니닐님다닥닦단닫달닭닮담답닷당닿대댁댐댓더덕던덜덟덤덥덧덩덮데델도독돈돌돕돗동돼되된두둑둘둠둡둥뒤뒷드득든듣들듬듭듯등디딩딪따딱딴딸땀땅때땜떠떡떤떨떻떼또똑뚜뚫뚱뛰뜨뜩뜯뜰뜻띄라락란람랍랑랗래랜램랫략량러럭런럴럼럽럿렁렇레렉렌려력련렬렵령례로록론롬롭롯료루룩룹룻뤄류륙률륭르른름릇릎리릭린림립릿링마막만많말맑맘맙맛망맞맡맣매맥맨맵맺머먹먼멀멈멋멍멎메멘멩며면멸명몇모목몬몰몸몹못몽묘무묵묶문묻물뭄뭇뭐뭘뭣므미민믿밀밉밌및밑바박밖반받발밝밟밤밥방밭배백뱀뱃뱉버번벌범법벗베벤벨벼벽변별볍병볕보복볶본볼봄봇봉뵈뵙부북분불붉붐붓붕붙뷰브븐블비빌빔빗빚빛빠빡빨빵빼뺏뺨뻐뻔뻗뼈뼉뽑뿌뿐쁘쁨사삭산살삶삼삿상새색샌생샤서석섞선설섬섭섯성세섹센셈셋셔션소속손솔솜솟송솥쇄쇠쇼수숙순숟술숨숫숭숲쉬쉰쉽슈스슨슬슴습슷승시식신싣실싫심십싯싱싶싸싹싼쌀쌍쌓써썩썰썹쎄쏘쏟쑤쓰쓴쓸씀씌씨씩씬씹씻아악안앉않알앓암압앗앙앞애액앨야약얀얄얇양얕얗얘어억언얹얻얼엄업없엇엉엊엌엎에엔엘여역연열엷염엽엿영옆예옛오옥온올옮옳옷옹와완왕왜왠외왼요욕용우욱운울움웃웅워원월웨웬위윗유육율으윽은을음응의이익인일읽잃임입잇있잊잎자작잔잖잘잠잡잣장잦재쟁쟤저적전절젊점접젓정젖제젠젯져조족존졸좀좁종좋좌죄주죽준줄줌줍중쥐즈즉즌즐즘증지직진질짐집짓징짙짚짜짝짧째쨌쩌쩍쩐쩔쩜쪽쫓쭈쭉찌찍찢차착찬찮찰참찻창찾채책챔챙처척천철첩첫청체쳐초촉촌촛총촬최추축춘출춤춥춧충취츠측츰층치칙친칠침칫칭카칸칼캄캐캠커컨컬컴컵컷케켓켜코콘콜콤콩쾌쿄쿠퀴크큰클큼키킬타탁탄탈탑탓탕태택탤터턱턴털텅테텍텔템토톤톨톱통퇴투툴툼퉁튀튜트특튼튿틀틈티틱팀팅파팎판팔팝패팩팬퍼퍽페펜펴편펼평폐포폭폰표푸푹풀품풍퓨프플픔피픽필핏핑하학한할함합항해핵핸햄햇행향허헌험헤헬혀현혈협형혜호혹혼홀홈홉홍화확환활황회획횟횡효후훈훌훔훨휘휴흉흐흑흔흘흙흡흥흩희흰히힘?!', help='character label')

    parser.add_argument('--sr_model_path', type=str, default=None, help='')
    parser.add_argument('--itt_model_path', type=str, default=None, help='')
    parser.add_argument('--yolo_model_path', type=str, default=None, help='')
    
    parser.add_argument('--font_path', type=str, default=None, help='')


    opt = parser.parse_args()

    opt.num_gpu = torch.cuda.device_count()

    demo(opt)
