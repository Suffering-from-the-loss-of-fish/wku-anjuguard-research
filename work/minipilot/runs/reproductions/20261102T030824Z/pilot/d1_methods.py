"""RGB association methods. This module never reads identity labels or pair answers."""
from __future__ import annotations
import ast, functools, hashlib, json, math, pathlib, time
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

def iou(a,b):
    xa,ya,xb,yb=a;xc,yc,xd,yd=b
    inter=max(0,min(xb,xd)-max(xa,xc))*max(0,min(yb,yd)-max(ya,yc))
    union=(xb-xa)*(yb-ya)+(xd-xc)*(yd-yc)-inter
    return inter/union if union>0 else 0.

def assignment(scores, minimum):
    """One-to-one maximum benefit assignment with independent unmatched dummies."""
    n,m=scores.shape
    if not n or not m:return set()
    benefit=np.zeros((n+m,n+m),dtype=float)
    benefit[:n,:m]=scores-minimum
    rows,cols=linear_sum_assignment(-benefit)
    return {(int(i),int(j)) for i,j in zip(rows,cols) if i<n and j<m and scores[i,j]>minimum}

@functools.lru_cache(maxsize=1)
def original_class(source):
    tree=ast.parse(pathlib.Path(source).read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AssessmentService')
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('_merge_cross_frame_candidates','_same_physical_risk')]
    module=ast.Module(body=[ast.ClassDef(name='Original',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
    ns={};exec(compile(ast.fix_missing_locations(module),source,'exec'),ns)
    return ns['Original']

def original_groups(observations,frames,source):
    original=original_class(str(source))();media={k:{'media_id':k,'source_id':v['source_id'],'captured_at_ms':v['captured_at_ms']} for k,v in frames.items()}
    groups=[];representatives=[]
    for o in observations:
        f=frames[o['frame_id']];x0,y0,x1,y1=o['bbox_xyxy']
        c={'observation_id':o['observation_id'],'risk_code':o['category'],'media_id':o['frame_id'],'confidence':1.,'evidence':'publisher bbox','region':{'type':'bbox','x':x0/f['width'],'y':y0/f['height'],'width':(x1-x0)/f['width'],'height':(y1-y0)/f['height']}}
        index=next((i for i,r in enumerate(representatives) if original._same_physical_risk(r,c,media)),None)
        if index is None:representatives.append(c);groups.append([o['observation_id']])
        else:groups[index].append(o['observation_id'])
    return groups

def quality(crop):
    gray=cv2.cvtColor(np.asarray(crop),cv2.COLOR_RGB2GRAY)
    sharp=float(cv2.Laplacian(gray,cv2.CV_64F).var())
    brightness=float(gray.mean())
    sharp_q=min(1.,math.sqrt(sharp/100.))
    size_q=min(1.,min(gray.shape)/64.)
    exposure_q=max(.2,1.-abs(brightness-127.5)/127.5)
    q=max(.15,min(1.,sharp_q*size_q*math.sqrt(exposure_q)))
    return {'quality':q,'laplacian_variance':sharp,'mean_brightness':brightness,'minimum_side_pixels':min(gray.shape)}

def geometry(left_image,right_image,left_boxes,right_boxes):
    """Automatic background reference matches, only used if a planar alignment passes checks.

    This is image-plane correspondence evidence, not a claim of stable 3-D geometry.
    No dataset poses, depth, object identity, or human relation annotation is used.
    """
    cv2.setNumThreads(1);cv2.setRNGSeed(1101)
    left=cv2.cvtColor(np.asarray(left_image),cv2.COLOR_RGB2GRAY)
    right=cv2.cvtColor(np.asarray(right_image),cv2.COLOR_RGB2GRAY)
    masks=[]
    for image,boxes in ((left,left_boxes),(right,right_boxes)):
        mask=np.full(image.shape,255,np.uint8)
        for x0,y0,x1,y1 in boxes:mask[max(0,y0-5):min(image.shape[0],y1+5),max(0,x0-5):min(image.shape[1],x1+5)]=0
        masks.append(mask)
    orb=cv2.ORB_create(nfeatures=1200)
    ka,da=orb.detectAndCompute(left,masks[0]);kb,db=orb.detectAndCompute(right,masks[1])
    meta={'valid':False,'reason':'insufficient_background_features','left_keypoints':len(ka),'right_keypoints':len(kb),'matches':0,'inliers':0}
    if da is None or db is None or len(da)<12 or len(db)<12:return None,meta
    knn=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da,db,k=2)
    matches=[a for pair in knn if len(pair)==2 for a,b in [pair] if a.distance<.7*b.distance]
    # Enforce unique destination keypoints before estimating reference geometry.
    unique={}
    for match in sorted(matches,key=lambda x:x.distance):unique.setdefault(match.trainIdx,match)
    matches=list(unique.values());meta['matches']=len(matches)
    if len(matches)<12:return None,meta
    src=np.float32([ka[m.queryIdx].pt for m in matches]);dst=np.float32([kb[m.trainIdx].pt for m in matches])
    h,mask=cv2.findHomography(src,dst,cv2.RANSAC,3.0,maxIters=2000,confidence=.995)
    if h is None or mask is None:return None,{**meta,'reason':'homography_failed'}
    inliers=mask.ravel().astype(bool);count=int(inliers.sum());meta.update(inliers=count,inlier_fraction=count/len(matches))
    if count<10 or count/len(matches)<.5:return None,{**meta,'reason':'weak_inlier_support'}
    transformed=cv2.perspectiveTransform(src.reshape(-1,1,2),h).reshape(-1,2)
    reproj=float(np.median(np.linalg.norm(transformed[inliers]-dst[inliers],axis=1)))
    span=np.ptp(src[inliers],axis=0)/np.array([left.shape[1],left.shape[0]])
    corners=np.float32([[0,0],[left.shape[1],0],[left.shape[1],left.shape[0]],[0,left.shape[0]]]).reshape(-1,1,2)
    warped=cv2.perspectiveTransform(corners,h)
    area=abs(float(cv2.contourArea(warped)))/(right.shape[0]*right.shape[1])
    meta.update(median_reprojection_pixels=reproj,inlier_span=span.tolist(),warped_area_ratio=area)
    if reproj>3 or min(span)<.2 or not .25<area<4 or not np.isfinite(h).all():return None,{**meta,'reason':'unstable_or_local_alignment'}
    return h,{**meta,'valid':True,'reason':'validated_approximate_planar_background_alignment','homography':h.tolist()}

def relation_scores(h,left,right,diagonal):
    scores=np.full((len(left),len(right)),.5,dtype=float)
    if h is None:return scores
    src=np.float32([[(x['bbox_xyxy'][0]+x['bbox_xyxy'][2])/2,(x['bbox_xyxy'][1]+x['bbox_xyxy'][3])/2] for x in left])
    dst=np.float32([[(x['bbox_xyxy'][0]+x['bbox_xyxy'][2])/2,(x['bbox_xyxy'][1]+x['bbox_xyxy'][3])/2] for x in right])
    if not len(src) or not len(dst):return scores
    projected=cv2.perspectiveTransform(src.reshape(-1,1,2),h).reshape(-1,2)
    distances=np.linalg.norm(projected[:,None,:]-dst[None,:,:],axis=-1)/diagonal
    return np.clip(1.-distances/.15,0,1)

def pair_margin(scores,matches,i,j,minimum):
    s=float(scores[i,j])
    if s<0:return -1.
    if (i,j) in matches:return max(0.,s-minimum)
    row_best=float(np.max(scores[i,:]));col_best=float(np.max(scores[:,j]))
    return -max(minimum-s,max(row_best,col_best)-s,.001)

def decide(margin,abstention):
    if abs(margin)+1e-12<abstention:return 'pending'
    return 'same' if margin>0 else 'different'
