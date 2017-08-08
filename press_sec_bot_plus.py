#!/usr/bin/env python
import sys
from datetime import date
from ConfigParser import SafeConfigParser
from subprocess import Popen, PIPE
from distutils.spawn import find_executable
from tempfile import NamedTemporaryFile
import twitter
import jinja2


def load_config():
    config = SafeConfigParser()
    if not config.read('press_sec_bot_plus.conf'):
        print "Couldn't load configuration."
        sys.exit(1)

    global api
    api = twitter.Api(
        consumer_key=config.get('twitter', 'consumer_key'),
        consumer_secret=config.get('twitter', 'consumer_secret'),
        access_token_key=config.get('twitter', 'access_token_key'),
        access_token_secret=config.get('twitter', 'access_token_secret'),
        tweet_mode='extended')


def render_tweet_html(tweet):
    date_format = '%B %-d, %Y'
    context = {
        'body': process_tweet_text(tweet),
        'date': date.fromtimestamp(tweet.created_at_in_seconds).strftime(date_format)
    }
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader('./')
    ).get_template('release_template.html').render(context)


def process_tweet_text(tweet):
    text = tweet.full_text

    for url in tweet.urls:
        text = text.replace(url.url, url.expanded_url)

    for media in tweet.media:
        text = text.replace(media.url, '')

    return jinja2.Markup(text.replace('\n', '<br>').strip())


def html_to_png(html):
    command = ['wkhtmltoimage']
    if not find_executable(command[0]):
        raise ImportError('%s not found' % command[0])

    command += ['-f', 'png'] # format output as PNG
    command += ['--zoom', '2'] # retina image
    command += ['--width', '750'] # viewport 750px wide
    command += ['-'] # read from stdin
    command += ['-'] # write to stdout

    wkhtml_process = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    (output, err) = wkhtml_process.communicate(input=html)

    output = set_retina_dpi(output)

    return output


def set_retina_dpi(png_bytes):
    command = ['convert']
    if not find_executable(command[0]):
        raise ImportError('ImageMagick not found')

    command += ['-units', 'PixelsPerInch']
    command += ['-density', '144'] # 144 seems to be required for Preview to show @2x
    command += ['-', '-'] # read and write to provided file_path

    convert_process = Popen(command, stdin=PIPE, stdout=PIPE)
    (output, err) = convert_process.communicate(input=png_bytes)

    return output

def release_tweet(tweet):
    """Formats and publishes a Tweet to the account"""
    tweet_html = render_tweet_html(tweet)
    image_data = html_to_png(tweet_html)

    status = ''
    media = []

    # Max 4 photos, or 1 video or 1 GIF

    for media_item in tweet.media:
        if media_item.type == 'video':
            status = '[Video: %s]' % media_item.expanded_url

        if media_item.type == 'animated_gif':
            status = '[GIF: %s]' % media_item.expanded_url

        if media_item.type == 'photo':
            if len(media) < 3:
                media.append(media_item.media_url_https)

                # Use large photo size if available
                if media_item.sizes.has_key('large'):
                    media[-1] += ':large'
            else:
                if status != '':
                    status += '\n'
                status += '[Photo: %s]' % media_item.expanded_url

    print status
    print media

    with NamedTemporaryFile(suffix='.png') as png_file:
        png_file.write(image_data)
        media.insert(0, png_file)
        api.PostUpdate(status=status, media=media)


def main():
    load_config()
    newest_tweet = api.GetUserTimeline(screen_name='@realDonaldTrump')[0]

    tweet_html = render_tweet_html(newest_tweet)
    image_file = html_to_png(tweet_html)

    print image_file


if __name__ == "__main__":
    main()
