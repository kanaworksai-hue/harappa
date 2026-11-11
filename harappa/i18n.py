# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""UI in English, 日本語, 简体中文 and 한국어.

1. Automatic: set Blender's language (Preferences > Interface > Translation) and Harappa follows,
   tooltips included, through Blender's own translation system.
2. By hand: the 🌐 menu in the panel header (or the add-on preferences) picks a language for the panel.
"""
import re

import bpy

PACKAGE = __package__

# msgid: (Japanese, Simplified Chinese, Korean)
UI = {
    # panels / sections
    "Harappa": ("原っぱ (Harappa)", "原野 (Harappa)", "들판 (Harappa)"),
    "Active Meadow": ("選択中の草原", "当前草地", "선택한 초원"),
    "Active Tree": ("選択中の木", "当前树木", "선택한 나무"),
    "Light & Sky": ("光と空", "光照与天空", "빛과 하늘"),
    "Brushwork": ("筆致", "笔触", "붓터치"),
    "Colours": ("色", "颜色", "색상"),
    "About": ("について", "关于", "정보"),
    "Grass": ("草", "草", "풀"),
    "Path": ("道", "小路", "길"),
    "Wind": ("風", "风", "바람"),
    "Flowers": ("花", "花", "꽃"),
    "Leaves": ("葉", "树叶", "잎"),
    "Tint": ("色味", "色调", "색조"),
    "Blossoms & Bark": ("花びらと幹", "花朵与树皮", "꽃잎과 줄기"),
    "Height": ("高さ", "高度", "높이"),
    "Hue Shift": ("色相のずれ", "色相偏移", "색상 이동"),
    "Brightness": ("明るさ", "亮度", "밝기"),
    "Black = bare path, white = grass": ("黒＝道（草なし）、白＝草", "黑色 = 小路（无草），白色 = 草",
                                         "검정 = 길 (풀 없음), 흰색 = 풀"),
    "Made for EEVEE (Anime Sky & Sun switches)": ("EEVEE 用です（「アニメの空と太陽」で切り替わります）",
                                                   "为 EEVEE 设计（点「动画天空与太阳」会自动切换）",
                                                   "EEVEE용입니다 (「애니 하늘과 태양」이 전환합니다)"),
    "Free add-ons (GitHub)": ("無料アドオン（GitHub）", "免费插件（GitHub）", "무료 애드온 (GitHub)"),
    "UI Language": ("表示言語", "界面语言", "표시 언어"),
    "Language of the Harappa panel. Automatic follows Blender's own language":
        ("Harappa パネルの表示言語。自動では Blender の言語設定に合わせます",
         "Harappa 面板的显示语言。自动 = 跟随 Blender 的语言设置",
         "Harappa 패널의 표시 언어. 자동은 Blender 언어 설정을 따릅니다"),
    "Automatic (follow Blender)": ("自動（Blender に合わせる）", "自动（跟随 Blender）", "자동 (Blender를 따름)"),
    "Auto": ("自動", "自动", "자동"),
    # scene settings
    "Season": ("季節", "季节", "계절"),
    "Colours, sunlight and sky": ("色・日差し・空", "颜色、阳光与天空", "색, 햇빛, 하늘"),
    "Paint Style": ("画風", "画风", "화풍"),
    "How the light and shadow are painted": ("光と影の描き方", "光影的画法", "빛과 그림자를 그리는 방식"),
    "Variation": ("バリエーション", "变体", "변형"),
    "Re-rolls colours, clumps, flowers, sun angle and each tree's tint around the current season and style. "
    "0 = off": ("いまの季節と画風のまま、色・草の塊・花・太陽の角度・木ごとの色味を振り直します。0 でオフ",
                "在当前季节和画风基础上，重新随机颜色、草团、花、太阳角度和每棵树的色调。0 = 关闭",
                "현재 계절과 화풍을 유지한 채 색·풀 덩어리·꽃·태양 각도·나무별 색조를 다시 뽑습니다. 0 = 끔"),
    "Sun Height": ("太陽の高さ", "太阳高度", "태양 높이"),
    "Sun elevation in degrees": ("太陽の仰角（度）", "太阳仰角（度）", "태양 고도 (도)"),
    "Sun Direction": ("太陽の向き", "太阳方向", "태양 방향"),
    "Sun angle around the camera in degrees (0 = behind the camera)":
        ("カメラを中心にした太陽の角度（度、0＝カメラの後ろ）", "绕相机的太阳角度（度，0 = 相机后方）",
         "카메라 기준 태양 각도 (도, 0 = 카메라 뒤)"),
    "Tree Shape": ("木の形", "树形", "나무 모양"),
    "Shape of the next tree": ("次に追加する木の形", "下一棵树的形状", "다음 나무의 모양"),
    "Tree Height": ("木の高さ", "树高", "나무 높이"),
    "Height of the next tree": ("次に追加する木の高さ", "下一棵树的高度", "다음 나무의 높이"),
    "Blossom": ("花の量", "花量", "꽃 양"),
    "Share of blossom dabs on the next tree": ("次の木の花の割合", "下一棵树上花朵笔触的比例",
                                               "다음 나무의 꽃 비율"),
    "Trees": ("本数", "棵数", "그루 수"),
    "How many trees Plant Trees adds": ("「木を植える」で追加する本数", "「种树」添加的数量",
                                        "「나무 심기」로 추가할 수"),
    "Paint": ("塗る", "绘制", "칠하기"),
    "What the brush paints": ("ブラシで塗るもの", "画笔绘制的内容", "브러시로 칠할 것"),
    "Paint grass back in": ("草を塗り戻します", "把草画回来", "풀을 다시 칠합니다"),
    "Paint a bare path": ("草のない道を塗ります", "绘制无草的小路", "풀 없는 길을 칠합니다"),
    # colours
    "Grass Lit": ("草（日なた）", "草（亮部）", "풀 (밝은 면)"),
    "Grass Patches": ("草（色むら）", "草（色块）", "풀 (색 얼룩)"),
    "Grass Shadow": ("草（影）", "草（阴影）", "풀 (그림자)"),
    "Grass Deep Shadow": ("草（濃い影）", "草（深阴影）", "풀 (짙은 그림자)"),
    "Grass Tips": ("草の先", "草尖", "풀끝"),
    "Path Lit": ("道（日なた）", "小路（亮部）", "길 (밝은 면)"),
    "Path Shadow": ("道（影）", "小路（阴影）", "길 (그림자)"),
    "Path Deep Shadow": ("道（濃い影）", "小路（深阴影）", "길 (짙은 그림자)"),
    "Leaves Lit": ("葉（日なた）", "树叶（亮部）", "잎 (밝은 면)"),
    "Leaves Mid": ("葉（中間）", "树叶（中间调）", "잎 (중간)"),
    "Leaves Shadow": ("葉（影）", "树叶（阴影）", "잎 (그림자)"),
    "Leaves Deep Shadow": ("葉（濃い影）", "树叶（深阴影）", "잎 (짙은 그림자)"),
    "Leaves Highlight": ("葉（ハイライト）", "树叶（高光）", "잎 (하이라이트)"),
    "Blossom Lit": ("花びら（日なた）", "花朵（亮部）", "꽃잎 (밝은 면)"),
    "Blossom Shadow": ("花びら（影）", "花朵（阴影）", "꽃잎 (그림자)"),
    "Bark Lit": ("幹（日なた）", "树皮（亮部）", "줄기 (밝은 면)"),
    "Bark Shadow": ("幹（影）", "树皮（阴影）", "줄기 (그림자)"),
    "Flower 1": ("花 1", "花 1", "꽃 1"),
    "Flower 2": ("花 2", "花 2", "꽃 2"),
    "Flower 3": ("花 3", "花 3", "꽃 3"),
    "Flower 4": ("花 4", "花 4", "꽃 4"),
    "Flower Centre": ("花の中心", "花心", "꽃 중심"),
    "Flower Shade": ("花の影色", "花的阴影色", "꽃 그림자 색"),
    "Sunlight Tint": ("日差しの色", "阳光色调", "햇빛 색조"),
    "Sky Top": ("空（上）", "天空（顶部）", "하늘 (위)"),
    "Blossom Deep Shadow": ("花びら（濃い影）", "花朵（深阴影）", "꽃잎 (짙은 그림자)"),
    "Cloud Lit": ("雲（日なた）", "云（亮部）", "구름 (밝은 면)"),
    "Cloud Shadow": ("雲（影）", "云（阴影）", "구름 (그림자)"),
    "Cloud Deep Shadow": ("雲（濃い影）", "云（深阴影）", "구름 (짙은 그림자)"),
    "Clouds": ("雲", "云", "구름"),
    "Haze": ("かすみ", "空气透视", "연무"),
    "Distant things fade towards the horizon colour (aerial perspective)":
        ("遠くのものほど地平線の色にかすみます（空気遠近法）", "越远的物体越接近地平线颜色（空气透视）",
         "먼 것일수록 지평선 색으로 흐려집니다 (대기 원근법)"),
    "Haze Start": ("かすみの始まり", "雾化起点", "연무 시작"),
    "Camera distance in metres where the haze begins": ("かすみが始まるカメラからの距離（m）", "雾化开始的相机距离（米）",
                                                        "연무가 시작되는 카메라 거리 (m)"),
    "Haze End": ("かすみの終わり", "雾化终点", "연무 끝"),
    "Camera distance in metres where the haze is full": ("かすみが最大になるカメラからの距離（m）",
                                                         "雾化达到最大的相机距离（米）", "연무가 최대가 되는 카메라 거리 (m)"),
    "Flower Brightness": ("花の明るさ", "花的亮度", "꽃 밝기"),
    "Rim Light": ("リムライト", "轮廓光", "림 라이트"),
    "Colour Strength": ("色の強さ", "色彩强度", "색 강도"),
    "Overall strength of every colour Harappa paints (1 = as set)": ("Harappa が描くすべての色の鮮やかさ（1 = 設定どおり）", "Harappa 画出的所有颜色的鲜艳程度（1 = 按设定）", "Harappa가 그리는 모든 색의 선명도 (1 = 설정 그대로)"),
    "Picture Contrast": ("全体のコントラスト", "整体对比度", "전체 대비"),
    "Overall contrast of everything Harappa paints (1 = as set)": ("Harappa が描くすべてのコントラスト（1 = 設定どおり）", "Harappa 画出的所有内容的对比度（1 = 按设定）", "Harappa가 그리는 모든 것의 대비 (1 = 설정 그대로)"),
    "Near Ridge": ("近くの山並み", "近处山脊", "가까운 능선"),
    "Middle Ridge": ("中ほどの山並み", "中间山脊", "중간 능선"),
    "Far Ridge": ("遠くの山並み", "远处山脊", "먼 능선"),
    "Cloud Rim": ("雲の縁", "云的金边", "구름 테두리"),
    "Cloud Rim Glow": ("雲の縁の輝き", "云边辉光", "구름 테두리 빛"),
    "Bright edge on clouds that have the sun behind them": ("太陽を背にした雲の縁が明るく光ります", "太阳在云后面时，云的边缘发亮", "해를 등진 구름의 가장자리가 밝게 빛납니다"),
    "Cloud Light / Shadow Split": ("雲の明暗の境目", "云的明暗分界", "구름 명암 경계"),
    "How much of each cloud is in shade": ("雲のどこまでを影にするか", "每朵云有多少处在阴影里", "구름의 어느 정도가 그늘인지"),
    "Warm light along the sun-facing edges of trees": ("木の、日の当たる側の輪郭にあたたかい光をのせます",
                                                       "在树朝向太阳一侧的轮廓上加暖色光",
                                                       "나무의 해를 향한 가장자리에 따뜻한 빛을 더합니다"),
    "Brightness of the meadow flowers (lower at night)": ("草原の花の明るさ（夜は低め）", "草地花朵的亮度（夜晚较低）",
                                                          "초원 꽃의 밝기 (밤에는 낮게)"),
    "Leaf Deep Split": ("葉の濃い影の境目", "树叶深阴影分界", "잎 짙은 그림자 경계"),
    "Below this light level leaves use the darkest colour": ("この明るさより暗い葉は一番濃い色になります",
                                                             "低于此亮度的树叶使用最深的颜色",
                                                             "이 밝기보다 어두운 잎은 가장 짙은 색을 씁니다"),
    "How many clouds Add Clouds builds (0 removes them)": ("「雲を追加」で作る雲の数（0 で削除）",
                                                           "「添加云」生成的云数量（0 = 删除）",
                                                           "「구름 추가」로 만들 구름 수 (0 = 삭제)"),
    "Sky Horizon": ("空（地平線）", "天空（地平线）", "하늘 (지평선)"),
    # tone / brushwork
    "Light / Shadow Split": ("光と影の境目", "明暗分界", "빛/그림자 경계"),
    "How much light a surface needs to count as lit": ("日なたになるのに必要な光の量", "表面被视为亮部所需的光量",
                                                       "밝은 면이 되는 데 필요한 빛의 양"),
    "Deep Shadow Split": ("濃い影の境目", "深阴影分界", "짙은 그림자 경계"),
    "Below this light level the darkest colour is used": ("この明るさより暗いところは一番濃い色になります",
                                                          "低于此亮度时使用最深的颜色",
                                                          "이 밝기보다 어두우면 가장 짙은 색을 씁니다"),
    "Edge Softness": ("境目のやわらかさ", "边缘柔和度", "경계 부드러움"),
    "Blend width of the cel edges": ("セルの境目のぼかし幅", "色阶边缘的过渡宽度", "셀 경계의 블렌드 폭"),
    "Clump Size": ("草の塊の大きさ", "草团大小", "풀 덩어리 크기"),
    "Size in metres of the light/shadow clumps painted across the grass":
        ("草原に描かれる光と影の塊の大きさ（m）", "草地上明暗草团的大小（米）", "풀밭에 그려지는 빛/그림자 덩어리 크기 (m)"),
    "Clump Strength": ("塊の強さ", "草团强度", "덩어리 강도"),
    "How strongly the clumps bend the light": ("塊がどれだけ光を曲げるか", "草团对光照的影响强度",
                                               "덩어리가 빛을 얼마나 꺾는지"),
    "Small Clumps": ("小さな塊", "小草团", "작은 덩어리"),
    "Amount of a second, smaller clump layer": ("もう一段小さい塊の量", "第二层更小草团的强度",
                                                "두 번째 작은 덩어리 층의 양"),
    "Brush Jitter": ("筆のゆらぎ", "笔触抖动", "붓 흔들림"),
    "Breaks shadow edges into blade-like strokes": ("影の境目を草の葉のような筆跡に崩します",
                                                    "把阴影边缘打散成草叶般的笔触",
                                                    "그림자 경계를 풀잎 같은 붓자국으로 깨뜨립니다"),
    "Dark Roots": ("根元の暗さ", "根部暗化", "뿌리 어둡게"),
    "Grass gets darker towards the ground": ("草が地面に近いほど暗くなります", "草越靠近地面越暗",
                                             "풀이 땅에 가까울수록 어두워집니다"),
    "Light Tips": ("明るい草先", "草尖提亮", "밝은 풀끝"),
    "Grass tips catch the light": ("草の先が光を受けて明るくなります", "草尖受光变亮", "풀끝이 빛을 받습니다"),
    "Wind Sheen": ("風の光", "风吹光泽", "바람 광택"),
    "Light waves that sweep across the grass with the gusts": ("風と一緒に草原を渡る光の波",
                                                               "随阵风扫过草地的光波",
                                                               "돌풍과 함께 풀밭을 지나가는 빛의 물결"),
    "Colour Patches": ("色むら", "色块", "색 얼룩"),
    "Large patches of the second grass colour": ("2 色目の草の大きな色むら", "第二种草色的大块色斑",
                                                 "두 번째 풀색의 큰 얼룩"),
    "Leaf Pockets": ("葉の奥の暗がり", "树叶暗部空隙", "잎 사이 어둠"),
    "Dark pockets between leaf clumps (ambient occlusion)": ("葉の塊の間の暗いくぼみ（アンビエントオクルージョン）",
                                                             "叶团之间的暗部（环境光遮蔽）",
                                                             "잎 덩어리 사이의 어두운 틈 (앰비언트 오클루전)"),
    "Leaf Highlights": ("葉のハイライト", "树叶高光", "잎 하이라이트"),
    "Bright highlight dabs on the sunniest leaves": ("いちばん日の当たる葉に明るいハイライト",
                                                     "在最受光的树叶上加亮色笔触",
                                                     "가장 햇빛 받는 잎에 밝은 하이라이트"),
    # seasons
    "Summer Meadow": ("夏の草原", "夏日草原", "여름 초원"),
    "Bright green hills, blue sky, white clouds of light": ("明るい緑の丘、青い空、まぶしい光",
                                                           "明亮的绿色山丘、蓝天与耀眼阳光",
                                                           "밝은 초록 언덕, 파란 하늘, 눈부신 빛"),
    "Spring Blossom": ("春の花", "春日花开", "봄꽃"),
    "Fresh yellow-greens, pink blossoms and pastel flowers": ("若々しい黄緑、ピンクの花、パステルの草花",
                                                             "清新的黄绿色、粉色花朵与粉彩小花",
                                                             "싱그러운 연두, 분홍 꽃, 파스텔 꽃"),
    "Golden Hour": ("夕暮れの金色", "黄金时刻", "골든아워"),
    "Low warm sun, golden grass, violet shadows": ("低く暖かい日差し、金色の草、すみれ色の影",
                                                  "低角度暖阳、金色草地、紫色阴影",
                                                  "낮고 따뜻한 햇살, 금빛 풀, 보랏빛 그림자"),
    "Autumn Leaves": ("秋の紅葉", "秋日红叶", "가을 단풍"),
    "Orange and red trees, dry golden grass": ("オレンジと赤の木、乾いた金色の草", "橙红色的树、干燥的金色草地",
                                               "주황과 빨강 나무, 마른 금빛 풀"),
    "Moonlit Night": ("月夜", "月夜", "달밤"),
    "Blue night meadow under a bright moon": ("明るい月の下の青い夜の草原", "明月下的蓝色夜晚草原",
                                              "밝은 달 아래 푸른 밤 초원"),
    "Misty Morning": ("霧の朝", "薄雾清晨", "안개 낀 아침"),
    "Soft pale greens and a hazy low-contrast light": ("やわらかく淡い緑と、かすんだ低コントラストの光",
                                                      "柔和浅绿与朦胧低对比的光线",
                                                      "부드럽고 옅은 초록과 흐릿한 저대비 빛"),
    # styles
    "Anime Background": ("アニメ背景", "动画背景", "애니 배경"),
    "Clean cel shading with broad grass clumps": ("大きな草の塊のすっきりしたセル塗り", "带大块草团的干净赛璐璐上色",
                                                  "큰 풀 덩어리의 깔끔한 셀 셰이딩"),
    "Painterly": ("絵画風", "绘画风", "회화풍"),
    "Broken, brushy shadow edges and lots of small clumps": ("筆跡の残る影の境目と、たくさんの小さな塊",
                                                             "笔触感的阴影边缘和大量小草团",
                                                             "붓자국 있는 그림자 경계와 많은 작은 덩어리"),
    "Crisp Cel": ("くっきりセル", "硬边赛璐璐", "선명한 셀"),
    "Hard two-tone edges, big graphic shapes": ("硬い 2 階調の境目と大きなグラフィックな形",
                                                "硬朗的双色边缘与大块图形",
                                                "딱딱한 2톤 경계와 큰 그래픽 형태"),
    "Soft Pastel": ("やわらかパステル", "柔和粉彩", "부드러운 파스텔"),
    "Gentle gradients, quiet shadows": ("やさしいグラデーションと静かな影", "柔和的渐变与安静的阴影",
                                       "부드러운 그라데이션과 차분한 그림자"),
    # trees
    "Round Tree": ("丸い木", "圆形树", "둥근 나무"),
    "A classic round broadleaf tree": ("定番の丸い広葉樹", "经典的圆形阔叶树", "전형적인 둥근 활엽수"),
    "Tall Tree": ("背の高い木", "高树", "키 큰 나무"),
    "A tall, narrow tree": ("細長く背の高い木", "高而窄的树", "높고 좁은 나무"),
    "Wide Tree": ("横に広い木", "宽冠树", "넓은 나무"),
    "A wide umbrella-shaped tree (cherry style)": ("横に広がる傘形の木（桜のような形）", "伞形宽冠树（樱花树形）",
                                                   "넓은 우산 모양 나무 (벚나무형)"),
    "Bush": ("茂み", "灌木", "덤불"),
    "A rounded bush without a visible trunk": ("幹の見えない丸い茂み", "看不到树干的圆形灌木",
                                               "줄기가 보이지 않는 둥근 덤불"),
    "Conifer": ("針葉樹", "针叶树", "침엽수"),
    "A pointed evergreen": ("とがった常緑樹", "尖顶常绿树", "뾰족한 상록수"),
    "Shape of this tree": ("この木の形", "这棵树的形状", "이 나무의 모양"),
    "Leaf Style": ("葉の形", "叶片样式", "잎 모양"),
    "Brush dab used for the leaves": ("葉に使う筆のタッチ", "树叶使用的笔触", "잎에 쓰는 붓터치"),
    "Round Leaves": ("丸い葉", "圆叶", "둥근 잎"),
    "Broad rounded leaf dabs": ("幅広の丸い葉のタッチ", "宽圆的叶片笔触", "넓고 둥근 잎 터치"),
    "Small Leaves": ("小さな葉", "小叶", "작은 잎"),
    "Many small leaf dabs": ("たくさんの小さな葉のタッチ", "大量细小的叶片笔触", "많은 작은 잎 터치"),
    "Needles": ("針葉", "针叶", "바늘잎"),
    "Thin needle strokes": ("細い針のようなタッチ", "细长的针状笔触", "가는 바늘 같은 터치"),
    "Tree height": ("木の高さ", "树高", "나무 높이"),
    "Seed": ("シード", "种子", "시드"),
    "Shape seed: each number is a different tree": ("形のシード：数字ごとに違う木になります",
                                                     "形状种子：每个数字都是一棵不同的树",
                                                     "모양 시드: 숫자마다 다른 나무가 됩니다"),
    # modifier inputs (Geometry Nodes)
    "Density": ("密度", "密度", "밀도"),
    "Height Random": ("高さのばらつき", "高度随机", "높이 무작위"),
    "Width": ("幅", "宽度", "너비"),
    "Edge Shrink": ("縁の草の低さ", "边缘草变矮", "가장자리 풀 낮추기"),
    "LOD Distance": ("間引き距離", "LOD 距离", "LOD 거리"),
    "Wind Strength": ("風の強さ", "风力", "바람 세기"),
    "Wind Speed": ("風の速さ", "风速", "바람 속도"),
    "Wind Scale": ("風の大きさ", "风的尺度", "바람 크기"),
    "Wind Direction": ("風向き", "风向", "바람 방향"),
    "Edge Wind": ("縁の揺れ", "边缘摆动", "가장자리 흔들림"),
    "Patch Size": ("群生の大きさ", "花丛大小", "군락 크기"),
    "Patch Amount": ("群生の量", "花丛数量", "군락 양"),
    "Size": ("大きさ", "大小", "크기"),
    "Leaf Size": ("葉の大きさ", "叶片大小", "잎 크기"),
    "Size Random": ("大きさのばらつき", "大小随机", "크기 무작위"),
    "Inflate": ("ふくらみ", "膨胀", "부풀리기"),
    "Roundness": ("まとまり", "整体圆润度", "둥글기"),
    "Blossom Scale": ("花のかたまりの大きさ", "花簇大小", "꽃 무리 크기"),
    "Fill Inside": ("内側を塗る", "填充内部", "안쪽 채우기"),
}

# operators: label / description
OPS = {
    "Make Anime Meadow": ("アニメの草原にする", "生成动画草原", "애니 초원 만들기"),
    "Grow anime grass and flowers on the selected meshes (or on a new hill when nothing is selected), and set "
    "up the sky and sun": ("選択中のメッシュにアニメの草と花を生やします（何も選んでいなければ新しい丘を作ります）。空と太陽も用意します",
                           "在选中的网格上长出动画风格的草和花（未选中时新建一座山丘），并设置天空和太阳",
                           "선택한 메시에 애니풍 풀과 꽃을 키웁니다 (선택이 없으면 새 언덕을 만듭니다). 하늘과 태양도 준비합니다"),
    "Flowers": ("花", "花", "꽃"),
    "Scatter flowers in the grass": ("草の中に花を散らします", "在草中散布花朵", "풀 속에 꽃을 흩뿌립니다"),
    "Grass tufts per square metre": ("1 ㎡あたりの草の株数", "每平方米的草丛数", "제곱미터당 풀포기 수"),
    "Grass Height": ("草の高さ", "草的高度", "풀 높이"),
    "Grass height in metres": ("草の高さ（m）", "草的高度（米）", "풀 높이 (m)"),
    "Add Anime Tree": ("アニメの木を追加", "添加动画树", "애니 나무 추가"),
    "Add an anime tree at the 3D cursor, standing on the ground below it":
        ("3D カーソルの位置に、地面に立つアニメの木を追加します", "在 3D 游标处添加一棵立在地面上的动画树",
         "3D 커서 위치에 땅에 선 애니 나무를 추가합니다"),
    "Shape of the tree": ("木の形", "树的形状", "나무 모양"),
    "Height of the tree": ("木の高さ", "树的高度", "나무 높이"),
    "Shape seed (-1 = random)": ("形のシード（-1 でランダム）", "形状种子（-1 = 随机）", "모양 시드 (-1 = 무작위)"),
    "Share of blossom dabs (-1 = use the panel value)": ("花のタッチの割合（-1 でパネルの値）",
                                                         "花朵笔触比例（-1 = 使用面板数值）",
                                                         "꽃 터치 비율 (-1 = 패널 값 사용)"),
    "Plant Trees": ("木を植える", "种树", "나무 심기"),
    "Scatter anime trees over the active meadow, keeping off painted paths":
        ("選択中の草原にアニメの木を散らして植えます（塗った道は避けます）", "在当前草地上散布动画树（避开画出的小路）",
         "선택한 초원에 애니 나무를 흩어 심습니다 (칠한 길은 피합니다)"),
    "How many trees to add": ("追加する本数", "添加的数量", "추가할 수"),
    "Placement seed": ("配置のシード", "摆放种子", "배치 시드"),
    "Average tree height": ("木の平均の高さ", "平均树高", "평균 나무 높이"),
    "Mix Shapes": ("形を混ぜる", "混合树形", "모양 섞기"),
    "Mix tree shapes; off = use the panel's tree shape": ("いろいろな形を混ぜます。オフならパネルの形だけ",
                                                         "混合多种树形；关闭 = 只用面板中的树形",
                                                         "여러 모양을 섞습니다. 끄면 패널의 모양만"),
    "New Shape": ("別の形にする", "换个形状", "다른 모양"),
    "Rebuild the active tree with a new random seed": ("選択中の木を新しいシードで作り直します",
                                                       "用新的随机种子重建当前树", "선택한 나무를 새 시드로 다시 만듭니다"),
    "New Seed": ("新しいシード", "新种子", "새 시드"),
    "Roll a new random seed": ("新しいシードを振ります", "随机一个新种子", "새 시드를 뽑습니다"),
    "Shape Canopy": ("樹冠を形づくる", "塑造树冠", "수관 다듬기"),
    "Edit the canopy clumps (move, scale or add spheres) — the leaves follow live. Shows the clump spheres while "
    "editing": ("樹冠の塊を編集します（球を移動・拡大・追加）。葉はリアルタイムでついてきます",
                "编辑树冠团块（移动、缩放或添加球体），树叶实时跟随", "수관 덩어리를 편집합니다 (구 이동·크기·추가). 잎이 실시간으로 따라옵니다"),
    "Make Foliage": ("葉っぱにする", "生成树叶", "잎으로 만들기"),
    "Cover the selected meshes with camera-facing anime leaf dabs (shape a bush, a hedge, a canopy — or a cloud — "
    "from any mesh)": ("選択中のメッシュを、カメラを向くアニメの葉のタッチで覆います（茂み・生け垣・樹冠、雲にも）",
                       "用朝向相机的动画树叶笔触覆盖选中网格（可做灌木、树篱、树冠，甚至云）",
                       "선택한 메시를 카메라를 향한 애니 잎 터치로 덮습니다 (덤불·울타리·수관, 구름도)"),
    "Anime Sky & Sun": ("アニメの空と太陽", "动画天空与太阳", "애니 하늘과 태양"),
    "Add Clouds": ("雲を追加", "添加云", "구름 추가"),
    "Build painted cumulus clouds in front of the scene camera (again to re-roll them)":
        ("シーンのカメラの前に、描いたような積雲を作ります（もう一度押すと作り直し）",
         "在场景相机前方生成手绘风积云（再点一次重新生成）", "씬 카메라 앞에 그림 같은 적운을 만듭니다 (다시 누르면 새로)"),
    "How many clouds": ("雲の数", "云的数量", "구름 수"),
    "Cloud seed (-1 = random)": ("雲のシード（-1 でランダム）", "云的种子（-1 = 随机）", "구름 시드 (-1 = 무작위)"),
    "Distance": ("距離", "距离", "거리"),
    "How far away the clouds float": ("雲までの距離", "云的距离", "구름까지의 거리"),
    "Switch to EEVEE with the Standard view, add the anime sky and a key sun":
        ("EEVEE と標準ビューに切り替え、アニメの空とキーの太陽を追加します",
         "切换到 EEVEE 和标准视图，添加动画天空和主光太阳", "EEVEE와 표준 뷰로 전환하고 애니 하늘과 키 태양을 추가합니다"),
    "Paint Grass": ("草を塗る", "画草", "풀 칠하기"),
    "Paint Path": ("道を塗る", "画小路", "길 칠하기"),
    "Vertex-paint where grass grows on the active meadow: black = bare path, white = grass":
        ("選択中の草原に、草の生える場所を頂点ペイントします（黒＝道、白＝草）",
         "在当前草地上用顶点绘制决定草的位置（黑 = 小路，白 = 草）",
         "선택한 초원에 풀이 자랄 곳을 버텍스 페인트합니다 (검정 = 길, 흰색 = 풀)"),
    "Value": ("値", "值", "값"),
    "Brush value (0 path, 1 grass)": ("ブラシの値（0 道、1 草）", "画笔数值（0 小路，1 草）", "브러시 값 (0 길, 1 풀)"),
    "Shuffle": ("シャッフル", "随机", "섞기"),
    "Roll a new variation of the current season and style": ("いまの季節と画風で新しいバリエーションを出します",
                                                             "在当前季节和画风下生成新变体",
                                                             "현재 계절과 화풍으로 새 변형을 뽑습니다"),
    "Reset to Defaults": ("初期設定に戻す", "恢复默认", "기본값으로"),
    "Summer Meadow, Anime Background style, no variation": ("夏の草原・アニメ背景・バリエーションなし",
                                                           "夏日草原、动画背景画风、无变体",
                                                           "여름 초원, 애니 배경, 변형 없음"),
    "Remove Grass": ("草を取り除く", "移除草", "풀 제거"),
    "Remove Harappa grass/flowers/foliage from the selected objects and restore their materials":
        ("選択中のオブジェクトから草・花・葉を取り除き、マテリアルを元に戻します",
         "从选中物体上移除草、花和树叶，并恢复原材质", "선택한 오브젝트에서 풀·꽃·잎을 제거하고 머티리얼을 되돌립니다"),
    "Set": ("設定", "设置", "설정"),
    "Choose this option": ("この項目を選びます", "选择此项", "이 항목을 선택합니다"),
}

REPORTS = [
    (r"Anime meadow on (\d+) object\(s\)", ("{0} 個のオブジェクトをアニメの草原にしました", "已在 {0} 个物体上生成动画草原",
                                            "오브젝트 {0}개를 애니 초원으로 만들었습니다")),
    (r"Tree added \(seed (\d+)\)", ("木を追加しました（シード {0}）", "已添加树（种子 {0}）", "나무를 추가했습니다 (시드 {0})")),
    (r"Planted (\d+) tree\(s\)", ("{0} 本の木を植えました", "已种下 {0} 棵树", "나무 {0}그루를 심었습니다")),
    (r"Foliage on (\d+) object\(s\)", ("{0} 個のオブジェクトを葉っぱにしました", "已为 {0} 个物体生成树叶",
                                       "오브젝트 {0}개를 잎으로 만들었습니다")),
    (r"Select one or more mesh objects", ("メッシュオブジェクトを選択してください", "请选择一个或多个网格物体",
                                          "메시 오브젝트를 선택하세요")),
    (r"Sky and sun ready", ("空と太陽の準備ができました", "天空和太阳已就绪", "하늘과 태양이 준비되었습니다")),
    (r"Paint the path in black, grass in white", ("道は黒、草は白で塗ってください", "用黑色画小路，白色画草",
                                                  "길은 검정, 풀은 흰색으로 칠하세요")),
    (r"Vertex Paint: pick black for paths, white for grass", ("頂点ペイント：道は黒、草は白を選んでください",
                                                              "顶点绘制：小路选黑色，草选白色",
                                                              "버텍스 페인트: 길은 검정, 풀은 흰색을 고르세요")),
    (r"(\d+) cloud\(s\) added", ("雲を {0} 個追加しました", "已添加 {0} 朵云", "구름 {0}개를 추가했습니다")),
    (r"Variation (\d+)", ("バリエーション {0}", "变体 {0}", "변형 {0}")),
    (r"Removed from (\d+) object\(s\)", ("{0} 個のオブジェクトから取り除きました", "已从 {0} 个物体移除",
                                          "오브젝트 {0}개에서 제거했습니다")),
    (r"Edit the clump spheres; Tab to finish", ("塊の球を編集してください。Tab で終了", "编辑团块球体，按 Tab 结束",
                                                "덩어리 구를 편집하세요. Tab으로 종료")),
]

LANGS = ("JA", "ZH", "KO")
_IDX = {"JA": 0, "ZH": 1, "KO": 2}


def prefs(context=None):
    try:
        addon = (context or bpy.context).preferences.addons.get(PACKAGE)
        return addon.preferences if addon else None
    except AttributeError:
        return None


def language():
    """EN / JA / ZH / KO for the panel: the 🌐 choice, else Blender's own language."""
    p = prefs()
    choice = getattr(p, "ui_language", "AUTO") if p else "AUTO"
    if choice != "AUTO":
        return choice
    view = bpy.context.preferences.view
    if not view.use_translate_interface:
        return "EN"
    loc = bpy.app.translations.locale or ""
    if loc.startswith("ja"):
        return "JA"
    if loc.startswith("zh_HANS") or loc.startswith("zh_CN"):
        return "ZH"
    if loc.startswith("ko"):
        return "KO"
    return "EN"


def t(msg):
    """Panel text in the chosen language. Draw it with translate=False so Blender leaves it alone."""
    lang = language()
    if lang == "EN":
        return msg
    row = UI.get(msg) or OPS.get(msg)
    return row[_IDX[lang]] if row else msg


def report(msg):
    lang = language()
    if lang == "EN":
        return msg
    for pattern, templates in REPORTS:
        m = re.fullmatch(pattern, msg)
        if m:
            return templates[_IDX[lang]].format(*m.groups())
    return msg


class HarappaPreferences(bpy.types.AddonPreferences):
    bl_idname = PACKAGE
    ui_language: bpy.props.EnumProperty(
        name="UI Language", default="AUTO",
        description="Language of the Harappa panel. Automatic follows Blender's own language",
        items=[("AUTO", "Auto", "Automatic (follow Blender)"), ("EN", "English", ""), ("JA", "日本語", ""),
               ("ZH", "简体中文", ""), ("KO", "한국어", "")])

    def draw(self, context):
        self.layout.prop(self, "ui_language")


def _dictionary():
    out = {"ja_JP": {}, "zh_HANS": {}, "ko_KR": {}}
    for table, ctxs in ((UI, ("*",)), (OPS, ("Operator", "*"))):
        for msg, row in table.items():
            for loc, text in zip(("ja_JP", "zh_HANS", "ko_KR"), row):
                for c in ctxs:
                    out[loc][(c, msg)] = text
    out["zh_CN"] = out["zh_HANS"]
    out["ja"] = out["ja_JP"]
    return out


def register():
    bpy.utils.register_class(HarappaPreferences)
    try:
        bpy.app.translations.register(PACKAGE, _dictionary())
    except ValueError:
        bpy.app.translations.unregister(PACKAGE)
        bpy.app.translations.register(PACKAGE, _dictionary())


def unregister():
    try:
        bpy.app.translations.unregister(PACKAGE)
    except ValueError:
        pass
    bpy.utils.unregister_class(HarappaPreferences)
