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
    # water
    "Water": ("水辺", "水", "물"),
    "Surface": ("水面", "水面", "수면"),
    "Banks": ("岸", "岸边", "물가"),
    "Add Pond": ("池を追加", "添加池塘", "연못 추가"),
    "Add Stream": ("小川を追加", "添加小溪", "개울 추가"),
    "Make Water from Curves": ("カーブを水にする", "把曲线变成水", "커브를 물로 만들기"),
    "Drop Onto Meadow": ("草原に沿わせる", "贴合到草地", "초원에 맞추기"),
    "Remove Water": ("水を削除", "删除水", "물 삭제"),
    "Depth": ("深さ", "深度", "깊이"),
    "Length": ("長さ", "长度", "길이"),
    "Shelf": ("浅瀬の幅", "浅滩宽度", "얕은 곳 폭"),
    "Flow Speed": ("流れの速さ", "流速", "흐름 속도"),
    "Bank": ("岸の幅", "岸边宽度", "물가 폭"),
    "Bank Height": ("岸の高さ", "岸边高度", "물가 높이"),
    "Slope": ("岸の傾き", "岸边坡度", "물가 경사"),
    "Water Shallow": ("水（浅い）", "水（浅处）", "물 (얕은 곳)"),
    "Water Mid": ("水（中間）", "水（中间）", "물 (중간)"),
    "Water Deep": ("水（深い）", "水（深处）", "물 (깊은 곳)"),
    "Water Foam": ("泡", "泡沫", "거품"),
    "Water Lines": ("水の線（光紋・流れ）", "水纹（光纹、水流）", "물결선 (빛무늬·흐름)"),
    "Water Reflection": ("水面の映り込み", "水面反光", "수면 반사"),
    "Water Shade": ("水の影", "水面阴影", "물 그림자"),
    "Caustics": ("水底の光紋", "水底光纹", "물밑 빛무늬"),
    "Rain Ripples": ("雨の波紋", "雨点波纹", "빗방울 물결"),
    "Glints": ("きらめき", "闪光点", "반짝임"),
    "Water Glow": ("水の発光", "水面发光", "물 발광"),
    "Rough radius of the pond": ("池のおおよその半径", "池塘的大致半径", "연못의 대략적인 반지름"),
    "Deepest point below the water line": ("水面からいちばん深いところまで", "水面到最深处的深度",
                                           "수면에서 가장 깊은 곳까지"),
    "Shape of the shoreline": ("岸の形", "岸线的形状", "물가 모양"),
    "Length of the new stream": ("新しい小川の長さ", "新小溪的长度", "새 개울의 길이"),
    "Stream width in metres": ("小川の幅（メートル）", "小溪宽度（米）", "개울 너비 (미터)"),
    "How far from the shore the bed reaches full depth": ("岸から何メートルで一番深くなるか", "离岸多远达到最深",
                                                         "물가에서 몇 미터 들어가야 가장 깊어지는지"),
    "Streams: metres per second": ("小川の流れ（メートル毎秒）", "小溪流速（米/秒）", "개울 흐름 (초당 미터)"),
    "Width of the bare bank beside the water": ("水辺の草のない岸の幅", "水边无草岸带的宽度", "물가의 풀 없는 둑 너비"),
    "How far the shore stands above the water line": ("岸が水面よりどれだけ高いか", "岸边高出水面多少",
                                                      "물가가 수면보다 얼마나 높은지"),
    "Steepness of the banks (rise per metre)": ("岸の傾き（1 メートルあたりの高さ）", "岸坡陡度（每米升高）",
                                                "둑의 경사 (미터당 높이)"),
    "The Harappa Water collection": ("Harappa Water コレクション", "Harappa Water 集合", "Harappa Water 컬렉션"),
    "Light net on the bottom of shallow water": ("浅いところの水底に揺れる光の網", "浅水底部晃动的光网",
                                                 "얕은 물 바닥에 일렁이는 빛 그물"),
    "How many raindrop rings spread on the water": ("水面に広がる雨粒の輪の量", "水面上扩散的雨点圆环数量",
                                                    "수면에 퍼지는 빗방울 고리의 양"),
    "Small sparkles of sunlight on the water": ("水面の小さな光のきらめき", "水面上的小闪光", "수면의 작은 햇빛 반짝임"),
    "Foam, ripples and the water itself give off light (night)": ("泡・波紋・水そのものが光ります（夜）",
                                                                  "泡沫、波纹和水本身会发光（夜晚）",
                                                                  "거품·물결·물 자체가 빛납니다 (밤)"),
    "A toon pond at the 3D cursor. It digs its own bed into the meadow and the grass steps back from the bank. "
    "Edit the curve to reshape it":
        ("3D カーソルの位置にトゥーン調の池を作ります。草原に池の底を掘り、岸の草は自然に退きます。カーブを編集すると形が変わります",
         "在 3D 游标处添加卡通池塘。它会在草地上挖出池底，岸边的草自动退开。编辑曲线即可改变形状",
         "3D 커서 위치에 툰 연못을 만듭니다. 초원에 바닥을 파고 물가의 풀은 물러납니다. 커브를 편집하면 모양이 바뀝니다"),
    "A winding toon stream starting at the 3D cursor and running away from the camera. It follows the meadow "
    "downhill and carves its own channel. Edit the curve, then Drop Onto Meadow":
        ("3D カーソルからカメラの奥へ流れる小川を作ります。草原の下り坂に沿って川底を掘ります。カーブを編集したら「草原に沿わせる」を押してください",
         "从 3D 游标开始、朝镜头前方蜿蜒的小溪。它沿着草地往低处流并挖出河道。编辑曲线后点「贴合到草地」",
         "3D 커서에서 카메라 안쪽으로 흐르는 개울을 만듭니다. 초원의 내리막을 따라 물길을 팝니다. 커브를 편집한 뒤 「초원에 맞추기」를 누르세요"),
    "Turn the selected curves into water: closed curves become ponds, open curves become streams (drawn from "
    "upstream to downstream)":
        ("選択中のカーブを水にします。閉じたカーブは池、開いたカーブは小川になります（上流から下流へ描いてください）",
         "把选中的曲线变成水：闭合曲线变成池塘，开放曲线变成小溪（从上游画到下游）",
         "선택한 커브를 물로 만듭니다. 닫힌 커브는 연못, 열린 커브는 개울이 됩니다 (상류에서 하류로 그리세요)"),
    "Lay the active stream back onto the meadow after editing it (running downhill only), or re-level an "
    "edited pond to its lowest rim; streams nearby join it again":
        ("編集した小川を草原の上に置き直します（下り方向だけに流れます）。編集した池は、縁のいちばん低い所に合わせて水位を直し、"
         "近くの小川もつなぎ直します",
         "编辑后把当前小溪重新贴合到草地上（只往低处流）；编辑过的池塘会按岸边最低处重新定水位，附近的小溪也会重新接上",
         "편집한 개울을 초원 위에 다시 놓습니다 (내리막으로만 흐릅니다). 편집한 연못은 가장자리의 가장 낮은 곳에 맞춰 수위를 "
         "고치고, 가까운 개울도 다시 잇습니다"),
    "Delete the active pond or stream; the meadow fills back in": ("選択中の池や小川を削除します。草原は元に戻ります",
                                                                  "删除当前的池塘或小溪，草地会恢复原样",
                                                                  "선택한 연못이나 개울을 삭제합니다. 초원은 원래대로 돌아옵니다"),
    "Water Type": ("水の種類", "水的类型", "물 종류"),
    "What kind of water this is": ("この水の種類", "这片水的类型", "이 물의 종류"),
    "Season Colours": ("季節の色", "季节配色", "계절 색"),
    "The water colours of the current season": ("いまの季節の水の色", "当前季节的水色", "지금 계절의 물 색"),
    "Clear Blue Lake": ("澄んだ青い湖", "清澈蓝湖", "맑고 푸른 호수"),
    "Clear, deep blue water with a bright sandy shelf": ("澄んだ深い青と、明るい砂の浅瀬", "清澈深蓝，浅滩明亮",
                                                         "맑고 깊은 파랑, 밝은 모래 얕은 곳"),
    "Lotus Pond": ("蓮の池", "荷塘", "연꽃 연못"),
    "Calm green water, a little cloudy: lily pads love it": ("少し濁った緑の静かな水。蓮の葉が好む池",
                                                             "微浊的绿色静水，荷叶最爱", "조금 탁한 초록빛 고요한 물, 연잎이 좋아하는 곳"),
    "Glacier Lake": ("氷河湖", "冰川湖", "빙하호"),
    "Milky turquoise water full of fine rock flour": ("細かな岩粉で乳白色に光るターコイズの湖", "细岩粉让湖水呈乳白碧绿",
                                                       "고운 암분으로 우윳빛이 도는 청록색 호수"),
    "Mountain Stream": ("山の清流", "山间清溪", "산골 맑은 물"),
    "Cold, glass-clear water: you see the bottom": ("冷たくガラスのように澄み、底まで見える水", "冰凉清澈，一眼见底",
                                                     "차갑고 유리처럼 맑아 바닥이 보이는 물"),
    "Tea-Brown Marsh": ("茶色い沼", "茶色沼泽", "찻빛 습지"),
    "Water stained brown by fallen leaves": ("落ち葉で茶色に染まった水", "被落叶染成茶色的水", "낙엽으로 갈색이 된 물"),
    "Hue Shift": ("色相", "色相偏移", "색조 이동"),
    "Shifts the colour of this water": ("この水の色合いをずらします", "改变这片水的色相", "이 물의 색조를 바꿉니다"),
    "Saturation": ("彩度", "饱和度", "채도"),
    "More or less colourful water": ("水の鮮やかさ", "水的鲜艳程度", "물의 선명함"),
    "Lighter or darker water": ("水の明るさ", "水的明暗", "물의 밝기"),
    "Clarity": ("透明度", "清澈度", "투명도"),
    "Clear water shows a wide bright shelf and caustics; murky water turns deep quickly":
        ("澄んだ水は明るい浅瀬と光の網が広く、濁った水はすぐ深い色になります", "清水浅滩宽、光纹多；浑水很快变深色",
         "맑은 물은 밝은 얕은 곳과 빛무늬가 넓고, 탁한 물은 금방 깊은 색이 됩니다"),
    "Scale this pond around its centre": ("池を中心から拡大・縮小します", "以中心缩放这个池塘", "연못을 중심에서 크기 조절합니다"),
    "Shape": ("形", "形状", "모양"),
    "A different shoreline for this pond (same size)": ("同じ大きさで岸の形を変えます", "保持大小，换一种岸线形状",
                                                        "같은 크기로 물가 모양을 바꿉니다"),
    "Add Rock": ("岩を追加", "添加岩石", "바위 추가"),
    "A painted rock with moss on top at the 3D cursor; grass and flowers grow around it. Press again for another "
    "shape": ("3D カーソルの位置に、苔の乗った絵画風の岩を置きます。草花は岩をよけて生えます。もう一度押すと別の形に",
              "在 3D 游标处放一块顶上长苔的手绘风岩石，草和花会绕开它生长。再按一次换一种形状",
              "3D 커서 위치에 이끼 낀 회화풍 바위를 놓습니다. 풀과 꽃은 바위를 피해 자랍니다. 다시 누르면 다른 모양"),
    "Rough size of the rock": ("岩のおおよその大きさ", "岩石的大致大小", "바위의 대략적인 크기"),
    "Flatness": ("平たさ", "扁平度", "납작함"),
    "Low and flat (small) or tall and round (large)": ("小さいと低く平ら、大きいと高く丸く", "数值小则低矮扁平，大则高而圆",
                                                       "작으면 낮고 납작하게, 크면 높고 둥글게"),
    "Shape seed (-1 = random)": ("形のシード（-1 でランダム）", "形状种子（-1 = 随机）", "모양 시드 (-1 = 무작위)"),
    "Lily Pads": ("蓮の葉", "荷叶", "연잎"),
    "How much of the floating-leaf zone the lily pads cover": ("浮葉の深さの帯を、蓮の葉がどれだけ覆うか",
                                                               "荷叶覆盖浮叶水深带的比例", "부엽 수심대를 연잎이 덮는 비율"),
    "Pad Size": ("葉の大きさ", "荷叶大小", "잎 크기"),
    "Lily pad radius": ("蓮の葉の半径", "荷叶半径", "연잎 반지름"),
    "Share of pads with a water-lily flower": ("睡蓮の花が咲く葉の割合", "开睡莲花的叶子比例", "수련 꽃이 피는 잎의 비율"),
    "Pebble Density": ("小石の量", "卵石密度", "자갈 밀도"),
    "Pebbles per square metre on the bank": ("岸 1 平方メートルあたりの小石の数", "岸边每平方米卵石数", "물가 1제곱미터당 자갈 수"),
    "Pebble Size": ("小石の大きさ", "卵石大小", "자갈 크기"),
    "Average pebble size": ("小石の平均の大きさ", "卵石平均大小", "자갈 평균 크기"),
    "Reeds": ("葦・ガマ", "芦苇和香蒲", "갈대·부들"),
    "Reed clumps per square metre in the shallows": ("浅瀬 1 平方メートルあたりの葦の株数", "浅水每平方米芦苇丛数",
                                                     "얕은 물 1제곱미터당 갈대 포기 수"),
    "Reed Height": ("葦の高さ", "芦苇高度", "갈대 높이"),
    "Height of the reeds": ("葦の高さ", "芦苇的高度", "갈대의 높이"),
    "Rocks": ("岩", "岩石", "바위"),
    "Rock Lit": ("岩（日なた）", "岩石（亮部）", "바위 (밝은 면)"),
    "Rock Patches": ("岩（まだら）", "岩石（斑块）", "바위 (얼룩)"),
    "Rock Shadow": ("岩（影）", "岩石（阴影）", "바위 (그림자)"),
    "Rock Deep Shadow": ("岩（濃い影）", "岩石（深阴影）", "바위 (짙은 그림자)"),
    "Moss": ("苔", "苔藓", "이끼"),
    "Moss on the tops of rocks, in the meadow's grass colours": ("岩の上の苔（草原の草の色）", "岩石顶上的苔藓（用草地的颜色）",
                                                                 "바위 위의 이끼 (초원 풀 색)"),
    "Add Waterfall": ("滝を追加", "添加瀑布", "폭포 추가"),
    "A waterfall whose plunge pool is at the 3D cursor: a raised terrace behind it, a stream across the top, a rock "
    "ledge it drops from, rock walls on both sides and foam at the foot. It faces the camera":
        ("3D カーソルの位置に滝つぼが来る滝を作ります。奥に高台、上を流れる小川、水が落ちる岩棚、両側の岩壁、足元の泡まで一式。カメラの方を向きます",
         "以 3D 游标为瀑布潭位置添加瀑布：后面是高台，上面有小溪流过，水从岩棚落下，两侧有岩壁，底部有泡沫。瀑布朝向镜头",
         "3D 커서 위치에 폭포 웅덩이가 오는 폭포를 만듭니다. 뒤쪽 고지, 위로 흐르는 개울, 물이 떨어지는 바위 턱, 양쪽 바위벽, 발치의 거품까지. 카메라 쪽을 향합니다"),
    "Height of the fall": ("滝の高さ", "瀑布高度", "폭포 높이"),
    "Width of the water at the lip": ("落ち口での水の幅", "瀑布口的水宽", "낙수 지점의 물 폭"),
    "Remove Waterfall": ("滝を削除", "删除瀑布", "폭포 삭제"),
    "Delete the whole waterfall the active object belongs to (terrace, stream, rocks, pool, sheet)":
        ("選択中のオブジェクトが属する滝を丸ごと削除します（高台・小川・岩・滝つぼ・水）",
         "删除当前物体所属的整个瀑布（高台、小溪、岩石、瀑布潭、水帘）",
         "선택한 오브젝트가 속한 폭포 전체를 삭제합니다 (고지·개울·바위·웅덩이·물줄기)"),
    "Weather": ("天気", "天气", "날씨"),
    "Clouds, rain or storm on top of the season": ("季節に重ねる、曇り・雨・嵐", "叠加在季节上的阴天、雨或暴风雨",
                                                   "계절 위에 더하는 흐림·비·폭풍"),
    "Clear": ("晴れ", "晴", "맑음"),
    "The season as it is": ("季節そのまま", "保持季节原样", "계절 그대로"),
    "Cloudy": ("曇り", "阴天", "흐림"),
    "Grey sky, soft light": ("灰色の空、やわらかな光", "灰色天空，柔和光线", "회색 하늘, 부드러운 빛"),
    "Rain": ("雨", "雨", "비"),
    "Rain streaks, raindrop rings on the water, a dim grey sky": ("雨のすじ、水面の雨粒の輪、ほの暗い灰色の空",
                                                                  "雨丝、水面雨点圆环、昏暗的灰色天空",
                                                                  "빗줄기, 수면의 빗방울 고리, 어스름한 회색 하늘"),
    "Storm": ("嵐", "暴风雨", "폭풍"),
    "Heavy rain and wind, a dark sky": ("激しい雨と風、暗い空", "大雨和大风，阴暗的天空", "거센 비와 바람, 어두운 하늘"),
    "How hard it rains (Rain and Storm)": ("雨の強さ（雨・嵐）", "雨量（雨和暴风雨）", "비의 세기 (비·폭풍)"),
    "Rain Area": ("雨の範囲", "下雨范围", "비 범위"),
    "Rain falls within this distance of the Harappa Rain object: move it to choose where it rains":
        ("Harappa Rain オブジェクトからこの距離の中に雨が降ります。動かすと降る場所を選べます",
         "雨落在 Harappa Rain 物体周围这个距离内：移动它就能决定在哪里下雨",
         "Harappa Rain 오브젝트에서 이 거리 안에 비가 내립니다. 옮기면 비 오는 곳을 고를 수 있습니다"),
    "Rainbow": ("虹", "彩虹", "무지개"),
    "A rainbow in the sky behind the scene": ("景色の奥の空に虹をかけます", "在场景后方的天空挂一道彩虹",
                                              "장면 뒤쪽 하늘에 무지개를 띄웁니다"),
    "Rainbow Strength": ("虹の濃さ", "彩虹强度", "무지개 세기"),
    "How bright the rainbow is": ("虹の明るさ", "彩虹的亮度", "무지개의 밝기"),
    "Fireflies": ("ホタル", "萤火虫", "반딧불이"),
    "Fireflies by the water (they glow at dusk and night)": ("水辺のホタル（夕方と夜に光ります）",
                                                            "水边的萤火虫（黄昏和夜晚发光）",
                                                            "물가의 반딧불이 (해 질 녘과 밤에 빛납니다)"),
    "Firefly Glow": ("ホタルの光", "萤火虫亮度", "반딧불이 빛"),
    "How brightly the fireflies glow (none by day)": ("ホタルの光の強さ（昼は光りません）", "萤火虫发光强度（白天不亮）",
                                                      "반딧불이 빛의 세기 (낮에는 빛나지 않음)"),
    "Add Koi": ("鯉を追加", "添加锦鲤", "잉어 추가"),
    "Koi swimming slow loops in the deep water of the active pond": ("選択中の池の深いところを、鯉がゆっくり回遊します",
                                                                    "锦鲤在当前池塘的深水处慢慢绕圈游",
                                                                    "선택한 연못의 깊은 곳을 잉어가 천천히 돕니다"),
    "Add Boat": ("小舟を追加", "添加小船", "작은 배 추가"),
    "A small wooden rowboat floating on the active pond (at the 3D cursor when it is on the water). Draft, bob and "
    "rock live on its Harappa Float modifier":
        ("選択中の池に木の小舟を浮かべます（3D カーソルが水の上ならその位置）。沈み具合・上下・揺れは Harappa Float モディファイアで",
         "在当前池塘上放一条木头小船（3D 游标在水面上时放在游标处）。吃水、上下浮动和摇晃在 Harappa Float 修改器里调",
         "선택한 연못에 나무 작은 배를 띄웁니다 (3D 커서가 물 위면 그 자리). 잠김·출렁임·흔들림은 Harappa Float 모디파이어에서"),
    "Draft": ("沈み具合（浮力）", "吃水（浮力）", "잠김 (부력)"),
    "How deep it sits in the water (buoyancy)": ("水にどれだけ沈むか（浮力）", "在水里沉多深（浮力）", "물에 얼마나 잠기는지 (부력)"),
    "Bob": ("上下の揺れ", "上下浮动", "출렁임"),
    "Up and down on the ripples": ("波で上下に揺れる量", "随波上下浮动的幅度", "물결에 위아래로 흔들리는 양"),
    "Sway": ("左右の揺れ", "左右摇晃", "좌우 흔들림"),
    "Rocking side to side (radians)": ("左右に揺れる量（ラジアン）", "左右摇晃幅度（弧度）", "좌우로 흔들리는 양 (라디안)"),
    "How fast it bobs": ("揺れの速さ", "摇晃速度", "흔들림 속도"),
    "Swimming speed (m/s)": ("泳ぐ速さ（m/秒）", "游动速度（米/秒）", "헤엄치는 속도 (m/초)"),
    "Fish length": ("魚の長さ", "鱼的长度", "물고기 길이"),
    "Count": ("数", "数量", "수"),
    "Speed": ("速さ", "速度", "속도"),
    "Freeze Banks": ("岸を固定", "固定岸边", "물가 고정"),
    "Update Banks": ("岸を更新", "更新岸边", "물가 갱신"),
    "Live Banks": ("岸をライブに", "岸边实时计算", "물가 실시간"),
    "Create": ("作る", "创建", "만들기"),
    "Selected Waterfall": ("選択中の滝", "选中的瀑布", "선택한 폭포"),
    "Selected Rock": ("選択中の岩", "选中的岩石", "선택한 바위"),
    "Selected Boat": ("選択中の小舟", "选中的小船", "선택한 작은 배"),
    "Selected Water": ("選択中の水", "选中的水", "선택한 물"),
    "Pond Life": ("水辺の生きもの", "池塘生物", "연못 생물"),
    "Shore (all ponds & streams)": ("岸辺（すべての池と小川）", "岸边（所有池塘和小溪）", "물가 (모든 연못과 개울)"),
    "All Water": ("すべての水", "所有水面", "모든 물"),
    "Fast Playback (Freeze Banks)": ("再生を軽く（岸を固定）", "加快播放（固定岸边）", "빠른 재생 (물가 고정)"),
    "Rain Here": ("ここに雨", "在这里下雨", "여기에 비"),
    "Make it rain only around the 3D cursor (inside the Rain Area circle); ponds outside stay calm. Turns Follow "
    "Camera off":
        ("3D カーソルのまわり（雨の範囲の円の中）だけに雨を降らせます。円の外の池は静かなまま。「カメラに追従」はオフになります",
         "只在 3D 游标周围（雨区圆圈内）下雨，圈外的池塘保持平静。会关闭“跟随相机”",
         "3D 커서 주변 (비 범위 원 안)에만 비가 내립니다. 원 밖의 연못은 잔잔합니다. '카메라 따라가기'는 꺼집니다"),
    "Firefly Colour": ("ホタルの色", "萤火虫颜色", "반딧불이 색"),
    "Dragonflies": ("トンボ", "蜻蜓", "잠자리"),
    "Dragonflies hovering over the ponds and streams, darting from spot to spot":
        ("池や小川の上でホバリングし、すいっと移動するトンボ", "在池塘和小溪上空悬停、忽然飞走的蜻蜓",
         "연못과 개울 위에서 머물다 휙 날아가는 잠자리"),
    "Add Stepping Stones": ("飛び石を追加", "添加踏脚石", "징검다리 추가"),
    "A row of flat stones across the active stream where it passes closest to the 3D cursor, their tops just above "
    "the water":
        ("3D カーソルに一番近いところで、選択中の小川を渡る平たい飛び石を並べます（水面から少し顔を出します）",
         "在选中小溪离 3D 游标最近的地方横着摆一排扁平的踏脚石（石头顶部略高于水面）",
         "3D 커서에 가장 가까운 곳에서 선택한 개울을 건너는 납작한 징검돌을 놓습니다 (물 위로 살짝 나옵니다)"),
    "Stones": ("石の数", "石头数量", "돌 수"),
    "How many stones (0 = enough to cross)": ("石の数（0 = 渡れるだけ自動）", "石头数量（0 = 自动铺满能走过去）",
                                             "돌 수 (0 = 건널 만큼 자동)"),
    "Could not find the stream near the 3D cursor": ("3D カーソルの近くに小川が見つかりません", "3D 游标附近找不到小溪",
                                                     "3D 커서 근처에서 개울을 찾을 수 없습니다"),
    "Spray mist rising at the foot": ("滝つぼから立ちのぼる水しぶきの霧", "瀑布底部升起的水雾", "폭포 아래에서 피어오르는 물안개"),
    "Mist": ("しぶき", "水雾", "물안개"),
    "Follow Camera": ("カメラに追従", "跟随相机", "카메라 따라가기"),
    "Grass Only in Camera View": ("カメラに映る所だけ草を生やす", "只在相机视野内长草", "카메라에 보이는 곳에만 풀"),
    "Grow grass and flowers only where the active camera can see (with a margin). Big scenes get much lighter and "
    "faster; the rendered picture stays the same":
        ("アクティブカメラに映る範囲（余白つき）だけに草と花を生やします。大きなシーンがずっと軽く速くなり、"
         "レンダリング結果は変わりません",
         "只在当前相机看得到的范围（留有余量）生成草和花。大场景会轻很多、快很多，渲染出来的画面不变",
         "활성 카메라에 보이는 범위(여유 포함)에만 풀과 꽃을 만듭니다. 큰 장면이 훨씬 가볍고 빨라지며, "
         "렌더링 결과는 같습니다"),
    "Rain over wherever the camera looks. Off: it rains only where Rain Here put the rain area":
        ("カメラが見ている所にいつも雨を降らせます。オフ：「ここに雨」で決めた場所だけに降ります",
         "相机看向哪里就在哪里下雨。关闭时：只在“在这里下雨”设定的位置下雨",
         "카메라가 보는 곳에 항상 비가 내립니다. 끄면: '여기에 비'로 정한 곳에만 내립니다"),
    "Size of the rain area (the circle in the viewport)": ("雨の範囲の大きさ（ビューポートの円）", "雨区大小（视口中的圆圈）",
                                                          "비 범위의 크기 (뷰포트의 원)"),
    "Fireflies glow at Golden Hour and Night: raise Firefly Glow for day":
        ("ホタルは夕暮れと夜に光ります。昼に光らせるなら「ホタルの光」を上げて", "萤火虫在黄昏和夜晚发光；白天要发光请调高“萤火虫亮度”",
         "반딧불이는 해질녘과 밤에 빛납니다. 낮에는 '반딧불이 빛'을 올리세요"),
    "Rock Size": ("岩の大きさ", "岩石大小", "바위 크기"),
    "Scale this rock": ("この岩の大きさを変えます", "缩放这块岩石", "이 바위의 크기를 바꿉니다"),
    "Low and flat (small) or tall and round (large)": ("小さいと低く平ら、大きいと高く丸く", "小＝低而扁，大＝高而圆",
                                                       "작으면 낮고 납작, 크면 높고 둥글게"),
    "A different shape for this rock": ("この岩の形を変えます", "换一个岩石形状", "이 바위의 다른 모양"),
    "Moss on this rock (the colour and overall amount are in Colours)":
        ("この岩のコケ（色と全体の量は「色」パネルで）", "这块岩石上的苔藓（颜色和整体量在“颜色”面板里）",
         "이 바위의 이끼 (색과 전체 양은 '색' 패널에서)"),
    "Flow": ("水量", "水量", "수량"),
    "How much water comes over the lip": ("滝口から落ちる水の量", "从瀑布口流下的水量", "폭포 입구로 떨어지는 물의 양"),
    "Height of the fall (rebuilds the waterfall's rocks and trees)": ("滝の高さ（滝の岩と木を作り直します）",
                                                                      "瀑布高度（会重建瀑布的岩石和树）",
                                                                      "폭포 높이 (폭포의 바위와 나무를 다시 만듭니다)"),
    "Width of the falling water (rebuilds the waterfall's rocks and trees)": ("落ちる水の幅（滝の岩と木を作り直します）",
                                                                              "落水宽度（会重建瀑布的岩石和树）",
                                                                              "떨어지는 물의 폭 (폭포의 바위와 나무를 다시 만듭니다)"),
    "Another arrangement of rocks and trees (rebuilds the waterfall)":
        ("岩と木の別の並び（滝を作り直します）", "换一种岩石和树的排列（会重建瀑布）", "바위와 나무의 다른 배치 (폭포를 다시 만듭니다)"),
    "Pond Scale": ("池の拡大率", "池塘缩放", "연못 배율"),
    "Scale this pond around its centre (x1 = as made)": ("池を中心から拡大・縮小（×1 = 作ったときの大きさ）",
                                                        "以中心缩放池塘（×1 = 创建时的大小）",
                                                        "연못을 중심에서 확대·축소 (×1 = 만들 때 크기)"),
    "Radius": ("半径", "半径", "반경"),
    "Heavy rain, strong wind in the grass and trees, a dark sky": ("強い雨、草と木を揺らす強風、暗い空",
                                                                   "大雨，草和树被强风吹动，天色昏暗",
                                                                   "강한 비, 풀과 나무를 흔드는 강풍, 어두운 하늘"),
    "Bake the dug banks of every meadow into the file so playback is fast. Harappa re-bakes after its own water "
    "tools; after editing a curve by hand press Update Banks":
        ("掘った岸をファイルに焼き込み、再生を速くします。Harappa の水ツールの後は自動で焼き直します。カーブを手で編集したら「岸を更新」を押してください",
         "把挖好的岸边烘焙进文件，让播放更流畅。Harappa 的水工具会自动重新烘焙；手动编辑曲线后请点「更新岸边」",
         "판 물가를 파일에 구워 재생을 빠르게 합니다. Harappa 물 도구 뒤에는 자동으로 다시 굽습니다. 커브를 직접 편집했다면 「물가 갱신」을 누르세요"),
    "Set": ("設定", "设置", "설정"),
    "Choose this option": ("この項目を選びます", "选择此项", "이 항목을 선택합니다"),
}

REPORTS = [
    (r"Banks are live while you paint \(Freeze Banks again when done\)",
     ("塗っている間は岸をライブにしました（終わったら「岸を固定」をもう一度）", "绘制期间岸边已切回实时（画完后再点「固定岸边」）",
      "칠하는 동안 물가를 실시간으로 바꿨습니다 (끝나면 「물가 고정」을 다시)")),
    (r"Trees don't grow in water: put the 3D cursor on dry ground",
     ("木は水の中には育ちません。3D カーソルを陸地に置いてください", "树不会长在水里：请把 3D 游标放到陆地上",
      "나무는 물속에서 자라지 않습니다. 3D 커서를 땅 위에 두세요")),
    (r"Make a meadow first: water carves its bed into the meadow",
     ("先に草原を作ってください（水は草原に底を掘ります）", "请先生成草地（水会在草地上挖出水底）",
      "먼저 초원을 만드세요 (물은 초원에 바닥을 팝니다)")),
    (r"Pond added", ("池を追加しました", "已添加池塘", "연못을 추가했습니다")),
    (r"Stream added", ("小川を追加しました", "已添加小溪", "개울을 추가했습니다")),
    (r"Select one or more curves", ("カーブを選択してください", "请选择一条或多条曲线", "커브를 선택하세요")),
    (r"(\d+) stepping stones", ("飛び石を {0} 個置きました", "放了 {0} 块踏脚石", "징검돌 {0}개를 놓았습니다")),
    (r"Could not find the stream near the 3D cursor", ("3D カーソルの近くに小川が見つかりません", "3D 游标附近找不到小溪",
                                                       "3D 커서 근처에서 개울을 찾을 수 없습니다")),
    (r"Water from (\d+) curve\(s\)", ("{0} 本のカーブを水にしました", "已把 {0} 条曲线变成水", "커브 {0}개를 물로 만들었습니다")),
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
