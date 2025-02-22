from bs4 import BeautifulSoup
import praw
import requests
import pandas as pd
import os
import html
import time
import re
from dotenv import load_dotenv

load_dotenv()

def fetch_reddit_posts(subreddit="politics", search_query="trump", limit=100):
    reddit = praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent=os.getenv('REDDIT_USER_AGENT')
    )

    posts = []
    for post in reddit.subreddit(subreddit).search(search_query, limit=limit):
        # Fetch comments
        post.comments.replace_more(limit=0)  # This removes "MoreComments" objects
        comments = []
        for comment in post.comments.list():
            comments.append({
                "comment_id": comment.id,
                "comment_text": comment.body,
                "comment_author": comment.author.name if comment.author else "Anonymous",
                "comment_score": comment.score,
                "comment_timestamp": comment.created_utc
            })

        posts.append({
            "platform": "Reddit",
            "id": post.id,
            "title": post.title,
            "content": post.selftext,
            "timestamp": post.created_utc,
            "comments_count": post.num_comments,
            "upvotes": post.score,
            "author": post.author.name if post.author else "Anonymous",
            "comments": comments
        })

    return posts

### 2. Fetch 4chan Data with Comments ###
def fetch_4chan_posts(boards=["pol"], search_query="trump"):
    posts = []
    for board in boards:
        catalog_url = f"https://a.4cdn.org/{board}/catalog.json"
        response = requests.get(catalog_url)
        catalog_data = response.json()

        for page in catalog_data:
            for thread in page['threads']:
                # Clean the content and title
                title = clean_html_text(thread.get('sub', ''))
                content = clean_html_text(thread.get('com', ''))

                if search_query.lower() in title.lower() or search_query.lower() in content.lower():
                    thread_id = thread['no']

                    thread_url = f"https://a.4cdn.org/{board}/thread/{thread_id}.json"
                    try:
                        thread_response = requests.get(thread_url)
                        thread_data = thread_response.json()

                        comments = []
                        for comment in thread_data['posts'][1:]:
                            clean_comment_text = clean_html_text(comment.get('com', ''))
                            comments.append({
                                "comment_id": comment['no'],
                                "comment_text": clean_comment_text,
                                "comment_author": "Anonymous",
                                "comment_timestamp": comment['time']
                            })

                        posts.append({
                            "platform": "4chan",
                            "id": thread_id,
                            "title": title,
                            "content": content,
                            "timestamp": thread['time'],
                            "comments_count": thread.get('replies', 0),
                            "upvotes": None,
                            "author": "Anonymous",
                            "comments": comments,
                            "topic": search_query,
                            "board": board
                        })
                    except:
                        continue

    return posts

### 3. Save Data ###
def save_data(data, search_query):
    # Create 'out' directory if it doesn't exist
    out_dir = 'out'
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        print(f"Created directory: {out_dir}")

    # Convert the nested comments structure to a string or separate files
    df = pd.DataFrame(data)

    # Add a timestamp to the file name
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    # Save main posts
    posts_df = df.drop('comments', axis=1)
    posts_filename = os.path.join(out_dir, f"{search_query}_posts_{timestamp}.csv")
    posts_df.to_csv(posts_filename, index=False)

    # Save comments separately
    comments_data = []
    for post in data:
        for comment in post['comments']:
            comment['post_id'] = post['id']
            comment['platform'] = post['platform']
            comments_data.append(comment)

    comments_df = pd.DataFrame(comments_data)
    comments_filename = os.path.join(out_dir, f"{search_query}_comments_{timestamp}.csv")
    comments_df.to_csv(comments_filename, index=False)

    print(f"Saved {len(posts_df)} posts and {len(comments_df)} comments in {out_dir}/")


def clean_html_text(text):
    if not text:
        return ""

    # First decode HTML entities
    text = html.unescape(text)

    # Remove all HTML tags
    soup = BeautifulSoup(text, 'html.parser')
    clean_text = soup.get_text(separator=' ')

    # Remove ">>" references
    clean_text = re.sub(r'>>\d+', '', clean_text)

    # Remove single ">" characters at the beginning of the text or after whitespace
    clean_text = re.sub(r'\s?>', '', clean_text)

    # Remove extra whitespace
    clean_text = ' '.join(clean_text.split())

    return clean_text

if __name__ == "__main__":
    SEARCH_QUERY = "trump"  # or any other topic you want to analyze
    CHANBOARDS = ["pol", "news", "int", "b"]

    print(f"Fetching Reddit posts about '{SEARCH_QUERY}'...")
    reddit_data = fetch_reddit_posts(search_query=SEARCH_QUERY, limit=100)
    print(f"Fetched {len(reddit_data)} Reddit posts")

    print(f"Fetching 4chan posts about '{SEARCH_QUERY}'...")
    chan_data = fetch_4chan_posts(boards=CHANBOARDS, search_query=SEARCH_QUERY)
    print(f"Fetched {len(chan_data)} 4chan posts")

    combined_data = reddit_data + chan_data

    save_data(combined_data, SEARCH_QUERY)
