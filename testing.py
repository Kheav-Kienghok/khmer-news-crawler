import csv

# Open the CSV file
with open('news_links.csv', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    urls = [row['URL'] for row in reader]

# Print the URLs
for url in urls:
    print(url)

print(len(urls))
