
# Source: https://gitlab.idiap.ch/bob/bob.paper.icassp2022_morph_generate


import os
import cv_utils
from PIL import Image
import pandas as pd
import numpy as np
import cv2 as cv
import dlib
import argparse
import time
from tqdm import tqdm
import auxiliary as aux

DLIB_LMD_PATH = "shape_predictor_68_face_landmarks.dat"

def parse_arguments():
    '''Parses in CLI arguments'''
    parser = argparse.ArgumentParser(
                    prog='opencv_morph.py',
                    description='A CLI tool for generating OpenCV morphed images of faces',
                    epilog='Disclaimer: this code comes from this reposioty: https://gitlab.idiap.ch/bob/bob.paper.icassp2022_morph_generate')

    parser.add_argument('-a', '--alpha', nargs=1, type=aux.check_float_range, default=[0.5], help="Provide the morphing's alpha value [0, 1] (default: 0.5)", required=False)

    requiredArgs = parser.add_argument_group('Required arguments')

    requiredArgs.add_argument('-s', '--src', type=aux.check_dir_path, help='Provide the folder path containing the raw images.', required=True)
    requiredArgs.add_argument('-m', '--morphed', type=aux.check_dir_path, help='Provide the folder path for the results.', required=True)
    requiredArgs.add_argument('-p', '--pairs', type=aux.check_dir_file, help='Provide the file path of the  `.csv` file containing the names of the pair of images to be morphed.', required=True)
    return parser.parse_args()


def make_opencv_morphs(PERMUTATIONS, SRC_DIR, dst_path, detector, predictor, fa, alpha):
    '''
    Loops over all given permutations to generate the opencv morph images.

    Source:
    -------
    Copyright (c) 2016 Satya Mallick <spmallick@learnopencv.com>
    All rights reserved. No warranty, explicit or implicit, provided.
    https://learnopencv.com
    '''
    print('Generating OpenCV morphs with alpha', alpha)

    failed_morphs = []
    
    # Loop with progressbar

    pbar = tqdm(total=len(PERMUTATIONS))
    for f1, f2 in PERMUTATIONS:

        try:

            #print('Morphing files:', f1, f2)
            # Read images
            img1 = np.array(Image.open(os.path.join(SRC_DIR, f1)))
            img2 = np.array(Image.open(os.path.join(SRC_DIR, f2)))
            # Convert from BGR to RGB
            img1 = cv.cvtColor(img1, cv.COLOR_BGR2RGB)
            img2 = cv.cvtColor(img2, cv.COLOR_BGR2RGB)
            # Get grayscale images
            #gray1 = cv.cvtColor(img1, cv.COLOR_RGB2GRAY)
            #gray2 = cv.cvtColor(img2, cv.COLOR_RGB2GRAY)
            # Get rectangles
            rects1 = detector(img1, 1)
            rects2 = detector(img2, 1)

            # Align images. It is assumed that images are already aligned
            #img1 = fa.align(img1, gray1, rects1[0])    # skipping this step as there is a bug in
            #img2 = fa.align(img2, gray2, rects2[0])    # imutils library. More here:
                                                        # https://stackoverflow.com/questions/70674243/how-to-detect-faces-with-imutils

            # We need the landmarks again as we have changed the size
            # rects1 = detector(img1, 1)
            # rects2 = detector(img2, 1)
            
            # Extract landmarks
            points1 = predictor(img1, rects1[0])
            points2 = predictor(img2, rects2[0])
            points1 = cv_utils.face_utils.shape_to_np(points1)
            points2 = cv_utils.face_utils.shape_to_np(points2)
            points = []
            # Compute weighted average point coordinates
            for i in range(0, len(points1)):
                x = (1 - alpha) * points1[i][0] + alpha * points2[i][0]
                y = (1 - alpha) * points1[i][1] + alpha * points2[i][1]
                points.append((x, y))
            # Allocate space for final output
            imgMorph = np.zeros(img1.shape, dtype=img1.dtype)
            # Rectangle to be used with Subdiv2D
            size = img1.shape
            rect = (0, 0, size[1], size[0])
            # Create an instance of Subdiv2D<
            subdiv = cv.Subdiv2D(rect)
            d_col = (255, 255, 255)
            # Calculate and draw delaunay triangles
            delaunayTri = cv_utils.calculateDelaunayTriangles(
                rect, subdiv, points, img1, 'Delaunay Triangulation', d_col, draw=False)
            # Morph by reading calculated triangles
            for line in delaunayTri:
                x, y, z = line
                x = int(x)
                y = int(y)
                z = int(z)
                t1 = [points1[x], points1[y], points1[z]]
                t2 = [points2[x], points2[y], points2[z]]
                t = [points[x],  points[y],  points[z]]
                # Morph one triangle at a time.
                cv_utils.morphTriangle(img1, img2, imgMorph, t1, t2, t, alpha)

            # Remove the black
            for i in range(len(imgMorph)):
                for j in range(len(imgMorph[i])):
                    if not np.any(imgMorph[i][j]):
                        imgMorph[i][j] = (1.0 - alpha) * \
                            img1[i][j] + alpha * img2[i][j]
                        
            # Save morphed image
            newname = os.path.join(dst_path, f1 + '_' + f2)
            #print(newname, imgMorph.shape)
            cv.imwrite(newname, imgMorph)

        except Exception:
            failed_morphs.append(f'{f1}_{f2}')

        finally:
            pbar.update(1)

    pbar.close()

    if len(failed_morphs) > 0:
        print("")
        print(f"{len(failed_morphs)} pairs of images could not be processed:")
        for text in failed_morphs:
            print(text)


def main():
    '''
    Makes OpenCV morphs between selected images given in the `.csv` file.
    '''

    # Parse arguments
    args = parse_arguments()
    
    # download dlib model
    aux.download_dlib_lmd(DLIB_LMD_PATH)
    
    # Define variables
    PERMUTATIONS  = pd.read_csv(args.pairs, header=None).values

    WIDTH         = 360
    HEIGHT        = 480

    # Instantiate dlib detector and predictors
    print('Instantiating modules.')
    detector  = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(DLIB_LMD_PATH)
    fa        = cv_utils.FaceAligner(predictor, desiredFaceWidth=WIDTH, desiredFaceHeight=HEIGHT)

    # OpenCV Morphs
    start = time.perf_counter()
    make_opencv_morphs(PERMUTATIONS, args.src, args.morphed, detector, predictor, fa, args.alpha[0])
    end = time.perf_counter()

    # Finish
    print(f'Job completed in {end - start}')


if __name__ == "__main__":
    main()