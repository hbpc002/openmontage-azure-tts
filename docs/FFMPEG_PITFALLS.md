# FFmpeg 视频生成避坑指南

## 1. 竖屏比例（9:16）不能直接缩放

```python
# ❌ 会拉伸变形
-vf "scale=1080:1920"

# ✅ scale+crop 先按比例缩放再裁剪
-vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"

# ✅ 或者 scale+pad 留黑边
-vf "scale=1080:1920:force_original_aspect_ratio=1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
```

## 2. Azure TTS 声音选择

| 场景 | 推荐 | 不推荐 |
|------|------|--------|
| 儿童教育 | `zh-CN-XiaochenMultilingualNeural`（阳光大姐姐） | `zh-CN-XiaoyiNeural`（太幼） |
| 正式旁白 | `zh-CN-YunxiNeural`（沉稳男声） | `zh-CN-XiaoxiaoNeural`（偏客服） |

- 使用 REST API 直接调用（`/cognitiveservices/v1`），不需要 `tts-express` 二进制
- SSML 里设 `<prosody rate="+15%">` 语速更快，适合儿童内容

## 3. drawtext 换行：用 textfile 不用 text

```python
# ❌ \n 会被原样显示出来
-vf "drawtext=text='第一行\n第二行'"

# ✅ 把文字写到文件里，用 textfile 读取
txt_a.write_text("第一行\n第二行", encoding="utf-8")
-vf "drawtext=textfile=/path/to/file.txt"
```

## 4. 文字动画：用 `alpha` + `enable` + `exp`

```python
# 滑入（exp(-5*t) 约 0.6 秒完成）
"y='H*0.25+(H+100)*exp(-5*t)'"

# 淡入
"alpha='min(1, 3*t)'"               # 0~0.33s 完成
"alpha='min(1, 3*(t-0.3))'"         # 延迟 0.3s 后淡入

# 注意：只有 text 模式下 alpha 才生效
# 如果用 textfile 参数，需要确保文字框启用
```

## 5. 视频素材 vs 图片素材

```python
# 视频需要 loop
"-stream_loop", "-1", "-i", clip_path  # 无限循环

# 图片需要 loop
"-loop", "1", "-i", image_path

# 两者都要加 -shortest 以音频长度为准截断
```

## 6. 音画同步：concat 陷阱

```python
# ❌ concat demuxer（-c copy）在不同编码参数的片段间会不同步
"-f concat -safe 0 -i list.txt -c copy"

# ✅ concat filter（重新编码）确保无缝拼接
# 每段单独生成（嵌入各自音频），最后用 filter 合并
"-filter_complex '[0:v][0:a][1:v][1:a]...concat=n=7:v=1:a=1[outv][outa]'"
```

## 7. 时长匹配：每段时长必须等于对应音频时长

```python
# 获取音频时长
dur = float(ffprobe_output)

# 视频段截断到音频时长
"-t", str(dur), "-shortest"
```

## 8. FFmpeg 调试技巧

```bash
# 查看合并后总时长是否等于各段之和
ffprobe -v error -show_entries format=duration output.mp4

# 查看视频编码参数是否一致
ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt seg*.mp4

# 逐段检查
for f in seg*.mp4; do echo "$f: $(ffprobe -v error -show_entries format=duration $f -of default=noprint_wrappers=1:nokey=1)s"; done
```

## 9. 每段嵌入自身音频（推荐做法）

与其最后拼音频，不如每段生成时就带上自己的音频：

```python
[
  "-i", video_source,        # 视频/图片
  "-i", audio_segment,       # 本段的音频
  "-vf", filter_string,      # 字幕动画
  "-c:a", "aac",             # 音频编码
  "-shortest",               # 以音频为准截断
]
```

这样每段内部音画天然同步，concat 时 v+a 一起拼，不会错位。
