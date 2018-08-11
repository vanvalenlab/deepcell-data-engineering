from universalmontagemaker import maker
from aws_upload import aws_upload
from montage_to_csv import montage_creator
from fig_eight_upload import fig_eight
from contrast_adjustment import contrast
import sys
import shutil
import os

def main(argv):
    # folder = str(input('New folder name: '))
    # if os.path.exists('./' + folder):
    #     shutil.rmtree('./' + folder)
    # os.makedirs('./' + folder)
    # os.chdir('./' + folder)

    # print('Converting raw images into processed images...')
    # contrast()
    # print('Making montages from processed images...')
    # maker()
    # print('Finished montages. Uploading montages to AWS...')
    # aws_upload()
    # print('Finished uploading to AWS. Creating csv\'s...')
    # montage_creator()

    print('Finished making csv\'s. Creating jobs for Figure Eight...')
    fig_eight()
    print('Success!')



if __name__ == "__main__":
    main(sys.argv[1:])
