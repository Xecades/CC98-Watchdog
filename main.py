import time

from loguru import logger as L

from cc98 import CC98Client
from dingtalk import send_dingtalk_message

# Configuration
INTERVAL = 2 * 60
DEBUG = False
KEYWORDS = [
    "前端",
    "网页",
    "网站",
    "后端",
    "服务器",
    "开发",
    "程序",
    "fullstack",
    "frontend",
    "backend",
    "web",
    "js",
    "javascript",
    "typescript",
    "react",
    "vue",
    "angular",
    "node",
    "html",
]


def check_topic_condition(topic: dict) -> bool:
    """
    Check if the topic meets the criteria for notification.
    """
    board_id = topic.get("boardId")
    title = topic.get("title", "").lower()

    # 459 is 实习兼职
    if board_id == 459:
        if any(keyword in title for keyword in KEYWORDS):
            return True

    return False


def format_message(topic: dict, board_name: str, content: str) -> str:
    title = topic.get("title", "No Title")
    author = topic.get("userName", "Unknown")
    topic_id = topic.get("id")
    time_str = topic.get("time", "")[:19].replace("T", " ")

    # Truncate content if it's too long
    if len(content) > 500:
        content = content[:500] + "..."

    return (
        f"【CC98 新帖通知】\n"
        f"板块: {board_name}\n"
        f"标题: {title}\n"
        f"作者: {author}\n"
        f"时间: {time_str}\n"
        f"链接: https://www.cc98.org/topic/{topic_id}\n"
        f"----------------\n"
        f"{content}"
    )


def main():
    L.info("Starting CC98 Monitor...")

    client = CC98Client()
    if not client.login():
        L.error("Initial login failed. Exiting.")
        return

    # Initial fetch to set the baseline
    L.info("Initializing... fetching current new topics.")
    max_id = 0

    try:
        topics = client.get_new_topics(size=20)
        if topics:
            # Assuming topics are returned, we find the max ID to avoid alerting on old posts
            max_id = max(t.get("id", 0) for t in topics)
            L.info(f"Initialization complete. Current max topic ID: {max_id}")
        else:
            L.warning("No topics found during initialization.")

    except Exception as e:
        L.error(f"Failed to fetch initial topics: {e}")
        return

    while True:
        L.info(f"Sleeping for {INTERVAL} seconds...")
        time.sleep(INTERVAL)

        L.info("Checking for updates...")
        try:
            # Fetch new topics
            topics = client.get_new_topics(size=20)

            # If we got an empty list, it might be because the token expired.
            if not topics:
                L.warning("Fetch returned empty. Token might be expired. Attempting re-login...")
                if client.login():
                    topics = client.get_new_topics(size=20)

            if topics:
                new_max_id = max_id

                # Filter for topics newer than our last check
                new_topics = [t for t in topics if t.get("id", 0) > max_id]

                # Sort by ID ascending to send notifications in order
                new_topics.sort(key=lambda x: x.get("id", 0))

                for topic in new_topics:
                    t_id = topic.get("id", 0)

                    if check_topic_condition(topic):
                        board_id = topic.get("boardId")
                        board_name = client.get_board_name(board_id)

                        # Fetch topic content
                        content = "No content available."
                        try:
                            posts = client.get_posts(t_id, size=1)
                            if posts:
                                content = posts[0].get("content", "No content.")
                        except Exception as e:
                            L.error(f"Failed to fetch content for topic {t_id}: {e}")

                        msg = format_message(topic, board_name, content)

                        if DEBUG:
                            L.info(f"[DEBUG] Would send notification:\n{msg}")
                        else:
                            send_dingtalk_message(msg)
                    else:
                        board_id = topic.get("boardId")
                        board_name = client.get_board_name(board_id)
                        title = topic.get("title", "No Title")
                        L.info(f"Ignored: [{board_name}] {title} (ID: {t_id})")

                    # Update max_id as we process
                    if t_id > new_max_id:
                        new_max_id = t_id

                max_id = new_max_id
                L.info(f"Check complete. New max ID: {max_id}")
            else:
                L.warning("Still no topics after re-login.")

        except Exception as e:
            L.error(f"An error occurred during update check: {e}")
            # Don't crash the loop, just wait for next interval


if __name__ == "__main__":
    main()
