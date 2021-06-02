from PIL import Image, ImageDraw


def dashed_line(draw, bound, width=1, fill=None, scale=5):
    dx = scale if bound[2] > bound[0] else -scale
    dy = scale if bound[3] > bound[1] else -scale
    if bound[0] == bound[2]:
        for y in range(bound[1], bound[3], dy *2):
            draw.line((bound[0], y, bound[2], y+ dy), width=width, fill=fill)
    elif bound[1] == bound[3]:
        for x in range(bound[0], bound[2], dx * 2):
            draw.line((x, bound[1], x + dx, bound[3]), width=width, fill=fill)
    else:
        for x in range(bound[0], bound[2], dx * 2):
            for y in range(bound[1], bound[3], dy * 2):
                draw.line((x, y, x + dx, y + dy), width=width, fill=fill)


def dashed_rectangle(draw, bound, fill=None, outline=None, width=1, scale=5):
    dashed_line(draw, (bound[0], bound[1], bound[0], bound[3]), width=width, fill=outline, scale=scale)
    dashed_line(draw, (bound[0], bound[3], bound[2], bound[3]), width=width, fill=outline, scale=scale)
    dashed_line(draw, (bound[2], bound[3], bound[2], bound[1]), width=width, fill=outline, scale=scale)
    dashed_line(draw, (bound[2], bound[1], bound[0], bound[1]), width=width, fill=outline, scale=scale)


def annotate_rectangle(source_img, target_img, bound, outline=None, width=10, scale=5):
    im = Image.open(source_img)
    draw = ImageDraw.Draw(im)
    # draw.rectangle(reg_result.bound, fill=(255, 255, 0, 20), outline=(100, 100, 100))
    dashed_rectangle(draw, bound, outline=outline, width=width, scale=scale)
    im.save(target_img, quality=95)
