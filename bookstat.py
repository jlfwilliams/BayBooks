#!~/Code/PycharmProjects/BookReviewProjectV-3/venv/bin/python3

import math
import os.path
import click
import requests
from datetime import date
from operator import attrgetter

import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm


# from rauth.service import OAuth1Service, OAuth1Session


class Book:
    title = ''
    isbn = ''
    average_rating = 0.0
    ratings_count = 0
    num_per_star = []  # ie num_per_star[0] = total of 5 stars, num_per_star[1] total of 4 stars ect.
    bay_average_rating = 0
    months_since_added = 0
    page_count = 0
    average_words_per_page = 0
    priority = 0  # Priority = 2 * BayRating + (months_since_added/2)

    def __str__(self):
        return '{{Title = {0:25.25}, Priority = {1:.1f}, Bay Average = {2:.2f}, User Average = {3:.2f}, Months Since Added = {4:}}}' \
            .format(self.title, self.priority, self.bay_average_rating, self.average_rating, self.months_since_added)


def calculate_bay_rating(star_list):
    """
    http://www.evanmiller.org/ranking-items-with-star-ratings.html
    """
    # This whole function is magic. For a better explanation checkout the article above ^^ #
    # Here's the gist: This function takes a list of star ratings in descending order      #
    # and returns the lower bound of a bayesian confidence interval with z value of 2.     #
    # Yeah that was a lot of technical jargon. In plain english, the function takes star   #
    # rating values for a book, uses those ratings to determine what range the average     #
    # rating is likely to be in if more ratings were collected, and then in the interest   #
    # of being conservative returns the lower bound of that range.                         #

    n = sum(star_list)  # this is the total number of ratings
    k = len(star_list)  # this is the number of different possible values for a rating
    s = list(range(k, 0, -1))
    s2 = [sk ** 2 for sk in s]
    z = 2.00  # this determines how wide the range is (smaller number = more narrow range)

    def f(s, ns):
        N = sum(ns)
        K = len(ns)
        return sum(sk * (nk + 1) for sk, nk in zip(s, ns)) / (N + K)

    fsns = f(s, star_list)
    return fsns - z * math.sqrt((f(s2, star_list) - fsns ** 2) / (n + k + 1))


#   TODO: find ways to make the code faster
#   TODO: integrate amazon data
#   TODO: fix average information for entire book list
#   TODO: discover way to determine when new books need to be bought
#           1. Compare priority numbers of wants and haves
#           2. if the next highest book in wants is greater than next highest book in haves
#                   then return highest book in wants. This book should be acquired
#   TODO: make file output CSV instead of plain text
#   TODO: find a way to predict the search space size for tdqm progress bar
#   TODO: figure out oauth2.0 because emily is a secret atheist
#   TODO: figure out how to anonymize the program, names, app key, user ids
#   TODO: figure out how to create generic file storing
#   TODO: allow user to add new user names and ids to the program
#   TODO: create config file to store app key and user ids
#   TODO: might be able to store data in static database entry
#   TODO: store list books that dont have isbns and print them all at the end of the output
#   TODO: figure out how to run program remotely using virtual env

def write_booklist_to_csv(book_list):
    # make headers
    column_names = ['Title', 'isbn', 'Avg Rating', 'Ratings Count',
                    '5 star', '4 star', '3 star', '2 star', '1 star',
                    'Bay Avg', 'Months in List', 'Priority', 'Page Count', 'Avg words per page']
    # make tuple data list
    data = []
    for book in book_list:
        book_tuple = (book.title, book.isbn, book.average_rating, book.ratings_count, book.num_per_star[0],
                      book.num_per_star[1], book.num_per_star[2], book.num_per_star[3], book.num_per_star[4],
                      book.bay_average_rating, book.months_since_added, book.priority, book.page_count,
                      book.average_words_per_page)
        data += [book_tuple]
    # make dataframe
    df = pd.DataFrame(data=data, columns=column_names)
    # write to csv
    df.to_csv('books.csv', index=False, header=True)


@click.command()
@click.option('--user', '-r', default='Finn', type=str, help='Define user string.')
@click.option('--update', '-u', is_flag=True, help='Force an update of data.')
@click.option('--want', '-w', is_flag=True, help='Specify that wants should be included in data.')
@click.option('--have', '-h', is_flag=True, help='Specify that haves should be included in data.')
def retrieve_rating_data(user, update, want, have):
    # stores all book objects
    book_list = []

    # creates a filename based on the specified commandline options
    filename = create_filename(have, user, want)

    # if update has been specified, then perform goodreads request and update file content
    if update or not os.path.isfile(filename):

        # retrieves goodreads book data
        goodreads_data_request(book_list, user, want, have)

        # passes goodreads data to a function that returns the bayesian rating
        for book in book_list:
            # if book isbn was not found then information is lacking so dont bother calculating the bay rate
            if book.isbn is not None:
                book.priority = calculate_priority(book)
    # else:
    #     df = pd.read_csv('./books.csv')
    #     book_list = []
    #     for row in df.items():
    #         row['Title']

    # sort the book list by bay rating
    book_list.sort(key=attrgetter('priority'), reverse=True)

    write_booklist_to_file(book_list, filename)

    write_booklist_to_csv(book_list)

    print_file_contents(filename)


def calculate_priority(book):
    # This is a special function designed to limit the contribution of time the #
    # longer the book remains on the shelf. It's a modified log base 2 function #
    # with some tuning hard coded tuning values. The returns a priority number  #
    # with a max value of 20 and a theoretical minimum of 2. The bay average    #
    # contributes a maximum of 10 points while the log function it self is also #
    # limited to 10.                                                            #
    book.bay_average_rating = calculate_bay_rating(book.num_per_star)
    ##### Traditional log graph priority function ####
    shift_up_down = -40
    shift_left_right = 3
    bend = 25
    angle = 5.3
    priority = 2 * book.bay_average_rating + \
               ((bend * math.log(book.months_since_added + shift_left_right)) + shift_up_down) / angle
    #################################################

    ##### HRRN sheduling alg priority function #####
    # calculate service time
    # words_per_month = 1500 * 30
    # service_time_in_months = (book.page_count * book.average_words_per_page) / words_per_month
    # # calculate ratio (wait + service) / service
    # if service_time_in_months > 0:
    #     ratio = (book.months_since_added + service_time_in_months) / service_time_in_months
    # else:
    #     ratio = book.months_since_added / 3
    # priority = ratio * 2 + book.bay_average_rating
    ################################################
    return priority


def write_booklist_to_file(book_list, filename):
    with open(filename, 'w') as outputFile:
        # write total num of books in list to the file
        outputFile.write('There are ' + str(len(book_list)) + ' books in the list.\n')

        # prints to file formatted information of books
        for book in book_list:
            outputFile.write(book.__str__() + '\n')


def print_file_contents(filename):
    # opens file with book information for specified user and option and prints to console
    with open(filename, 'r') as outputFile:
        for line in outputFile:
            print(line)


def create_filename(have, user, want):
    filename = '/Users/cubes/Documents/BookRatingFiles/' + user + 'books-'
    if want and have:
        filename += 'all.txt'
    elif want:
        filename += 'want.txt'
    elif have:
        filename += 'have.txt'
    else:
        filename += 'have.txt'
    return filename


# Retrieves book data as well as reviews from www.goodreads.com
def goodreads_data_request(book_list, user, want, have):
    # goodreads app key
    CONSUMER_KEY = "BnMEJUN4pCVlc4jNmrvg"
    CONSUMER_SECRET = "OgBoemCyEMgSb4xep6t3EiN7ye8zfFdCvimHbTnX0"

    # goodreads = OAuth1Service(
    #     consumer_key=CONSUMER_KEY,
    #     consumer_secret=CONSUMER_SECRET,
    #     name='goodreads',
    #     request_token_url='https://www.goodreads.com/oauth/request_token',
    #     authorize_url='https://www.goodreads.com/oauth/authorize',
    #     access_token_url='https://www.goodreads.com/oauth/access_token',
    #     base_url='https://www.goodreads.com/'
    # )
    #
    # request_token, request_token_secret = goodreads.get_request_token(header_auth=True)
    #
    # authorize_url = goodreads.get_authorize_url(request_token)
    # print('Visit this URL in your browser: ' + authorize_url)
    # accepted = 'n'
    # while accepted.lower() == 'n':
    #     # you need to access the authorize_link via a browser,
    #     # and proceed to manually authorize the consumer
    #     accepted = raw_input('Have you authorized me? (y/n) ')

    # dictionary of dates for parsing of date string
    date_dict = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12
    }

    # check to see if user was specified # goodreads user id #Emily: 91493354 #Finn: 58961242
    if user == 'Finn':
        user_id = "58961242"
    elif user == 'Emily':
        user_id = '91493354'
    # default to this value
    else:
        user_id = "58961242"  # Finn's ID

    page = 1
    page_full = True
    while page_full:
        owned_book_url = "https://www.goodreads.com/review/list?v=2&key=" + CONSUMER_KEY \
                         + "&id=" + user_id + "&shelf=to-read&sort=owned&per-page=100&page=" + str(page)
        owned_book_response = requests.get(owned_book_url)
        owned_book_xml = BeautifulSoup(owned_book_response.content, "xml")

        # loop through all review entries and retrieve books
        counter = len(book_list)
        review_list = owned_book_xml.find_all("review")

        if len(review_list) <= 0:
            page_full = False

        def parser_helper(book_list):
            book_list.append(Book())
            book_list[counter].title = review.book.title.string
            book_list[counter].isbn = review.book.isbn.string
            book_list[counter].average_rating = float(review.book.average_rating.string)
            book_list[counter].ratings_count = int(review.book.ratings_count.string)
            # parses date string
            # 'Wed May 29 20:22:48 -0700 2019'
            raw_date_string = review.date_added.string
            # ['Wed', 'May', '29', '20:22:48', '-0700', '2019']
            date_list = raw_date_string.split(' ')
            now = date.today()
            # '2019'
            year_added = date_list[5]
            year_now = now.year
            # 'May': 5
            month_added = date_dict[date_list[1]]
            month_now = now.month
            book_list[counter].months_since_added = ((int(year_now) - int(year_added)) * 12
                                                     + int(month_now) - int(month_added))

        for review in review_list:

            if have and want:  # collect both owned and not owned books on the to-read list
                parser_helper(book_list)
                counter += 1

            elif have:  # collect just the owned
                # goodreads marks books with >=1 if owned and 0 if not
                if review.owned.string == "1":
                    parser_helper(book_list)
                    counter += 1
                else:
                    page_full = False
                    continue
            elif want:  # collect just the not owned
                # goodreads marks books with a value >= 1 if owned and 0 if not
                if review.owned.string == "0":
                    parser_helper(book_list)
                    counter += 1

        page += 1

    for book in tqdm(book_list, desc='Getting review data', leave=False):
        # error checking for books that don't have isbns
        if not isinstance(book.isbn, str):
            print(type(book.isbn))
            print(book.title)
            print(book.isbn)
        else:
            book_by_isbn_url = "https://www.goodreads.com/book/isbn/" + book.isbn + "?key=" + CONSUMER_KEY
            book_by_isbn_response = requests.get(book_by_isbn_url)
            book_by_isbn_xml = BeautifulSoup(book_by_isbn_response.content, 'xml')

            # Start with a string like this -> '5:32809|4:2342|3:23423|2:2342|1:23423|total:78234234'
            rating_string = book_by_isbn_xml.find('work').rating_dist.string
            # turn the string into a list -> ['5:32809','4:2342','3:23423','2:2342','1:23423','total:78234234']
            rating_list = rating_string.split('|')
            # remove the unneeded 'total element' -> ['5:32809','4:2342','3:23423','2:2342','1:23423']
            rating_list.pop()
            # format the strings by removing the leading rating identifiers -> ['32809','2342','23423','2342','23423']
            for index in range(len(rating_list)):
                rating_list[index] = int(rating_list[index][2:])  # slices off the "5:" format for each item in list
            # add the formatted review list to the book object
            book.num_per_star = rating_list


# Retrieves additional reviews from www.amazon.com
def amazon_data_request(book_list):
    headers = {
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.45 Safari/535.19'}

    for book in book_list:
        amazon_url = 'http://www.amazon.com/dp/' + book.isbn


if __name__ == '__main__':
    retrieve_rating_data()
