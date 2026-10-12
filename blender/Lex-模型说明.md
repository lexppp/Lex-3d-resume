# Lex 人物源文件

lex.blend 是可编辑的 Blender 4.5 场景：独立人物部件、贴纸网格、已打包的透明纹理、CameraAction 相机动画和焦点空对象。

在 Blender 中修改贴纸：选中 decal_Lex_00…09，移动 / 旋转或编辑网格 UV 可以更换图集单元；贴纸已按脸部曲面贴合。修改位置后，可用 Shrinkwrap 将贴纸投射到 LexFace，并设置 0.0028 左右的表面偏移。

导出时保留相机、NLA CameraAction 动画、24 fps 和 focus-0、focus-1…5、focus-works 空对象，输出到 web/public/models/lex.glb。

复现现有模型（项目根目录作为最后一个参数）：

blender --background --python blender/create_lex.py -- "你的项目根目录"

贴纸来自内置 image_gen 生成的 16 图案透明 PNG。提示词主题：微笑、星星、行星、闪电、游戏手柄、心、幽灵、火箭、花、耳机、灯泡、樱桃、代码括号、骰子、蘑菇、纸飞机；4×4 宫格，无文字品牌，白色模切边。

当前种子：20261013，布局参数在 lex-sticker-layout.json。更改 create_lex.py 的 SEED 即可重新随机选择与分布。