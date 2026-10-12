"""Build a photo-guided, stylized Lex bust and surface-conforming stickers.

Run with Blender 4.5 in background. The source photo is used as an artist's
reference, not embedded into the public model or represented as a scan.
Coordinates below use glTF's Y-up / +Z-front convention, converted for Blender.
"""
import bpy, math, random, json, struct, sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(sys.argv[sys.argv.index('--') + 1])
ASSET = ROOT / 'web/public/models'
BACKUP = ROOT / 'blender/lex-camera-rig.glb'
ATLAS = ROOT / 'blender/lex-stickers.png'
SEED = 20261013
rng = random.Random(SEED)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(BACKUP))
scene = bpy.context.scene
scene.frame_set(0)
camera = next(o for o in scene.objects if o.type == 'CAMERA')
scene.camera = camera
# Retain the imported camera animation and empty focus anchors, remove the old
# character, eyes and branded decals. Preserve each anchor's world transform.
anchors = [o for o in scene.objects if o.name.startswith('focus-')]
for o in anchors:
    world = o.matrix_world.copy()
    o.parent = None
    o.matrix_world = world
for o in list(scene.objects):
    if o.type == 'MESH':
        bpy.data.objects.remove(o, do_unlink=True)

def xyz(p):
    return (p[0], -p[2], p[1])

def material(name, color, rough=.45, metallic=0, alpha=1):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree.nodes.get('Principled BSDF')
    rgb = tuple(int(color[i:i+2],16)/255 for i in (1,3,5))
    # Convert sRGB input colors to Blender linear values.
    rgb = tuple(c/12.92 if c < .04045 else ((c+.055)/1.055)**2.4 for c in rgb)
    n.inputs['Base Color'].default_value = (*rgb,1)
    n.inputs['Roughness'].default_value = rough
    n.inputs['Metallic'].default_value = metallic
    n.inputs['Alpha'].default_value = alpha
    m.diffuse_color = (*rgb,alpha)
    if alpha < 1:
        m.surface_render_method = 'DITHERED'
    return m

skin = material('Lex warm skin','#d6a58a',.5)
skin.node_tree.nodes.get('Principled BSDF').inputs['Subsurface Weight'].default_value=.065
earskin = material('Lex ear warmth','#c58d78',.55)
lip = material('Lex lips','#a96865',.5)
mouthmat = material('Lex mouth line','#533632',.65)
white = material('Lex eye whites','#f5f2e9',.28)
iris = material('Lex dark brown iris','#493b30',.35)
pupil = material('Lex pupil','#13191b',.25)
teeth = material('Lex smile','#f4e8d8',.35)
shirt = material('Lex pale blue shirt','#bdcbd7',.78)
seam = material('Lex shirt seams','#9fafbc',.83)
collar = material('Lex collar','#d0dbe3',.73)
tie = material('Lex navy tie','#1a2639',.86)
silver = material('Lex silver glasses','#9ba7ac',.22,.8)
glass = material('Lex clear lenses','#eff3f5',.12,0,.025)
teal = material('Lex turquoise earring','#19a8ad',.26,.25)
hairmats = [material('Lex black hair '+str(i),c,.49) for i,c in enumerate(['#11151b','#141920','#171d24','#1b2129'])]

def finish(o,name,mat):
    o.name=name
    o.data.materials.append(mat)
    if o.type=='MESH':
        for p in o.data.polygons: p.use_smooth=True
    return o

def ellipsoid(name,center,radii,mat,segments=40,rings=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=xyz(center))
    o=bpy.context.object
    o.scale=(radii[0],radii[2],radii[1])
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,name,mat)

def mesh(name,verts,faces,mat,uv=None):
    d=bpy.data.meshes.new(name)
    d.from_pydata([xyz(v) for v in verts],[],faces)
    d.update()
    o=bpy.data.objects.new(name,d)
    scene.collection.objects.link(o)
    finish(o,name,mat)
    if uv:
        layer=d.uv_layers.new(name='UVMap')
        for polygon in d.polygons:
            for loop_index in polygon.loop_indices:
                layer.data[loop_index].uv=uv[d.loops[loop_index].vertex_index]
    return o

def tube(name,points,radius,mat,cyclic=False):
    curve=bpy.data.curves.new(name,'CURVE')
    curve.dimensions='3D'
    curve.resolution_u=10
    curve.bevel_depth=radius
    curve.bevel_resolution=3
    spline=curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    for b,p in zip(spline.bezier_points,points):
        b.co=xyz(p)
        b.handle_left_type=b.handle_right_type='AUTO'
    spline.use_cyclic_u=cyclic
    o=bpy.data.objects.new(name,curve)
    scene.collection.objects.link(o)
    curve.materials.append(mat)
    # Export as actual mesh, all pieces remain independently editable in .blend.
    bpy.context.view_layer.objects.active=o
    o.select_set(True)
    bpy.ops.object.convert(target='MESH')
    o.select_set(False)
    return o

# Photo-guided oval face: narrower lower jaw, broad cheeks, rounded chin.
PROFILE=[(.10,.018,.065,-.035),(.14,.088,.106,-.022),(.20,.160,.154,-.02),(.28,.218,.190,-.027),(.38,.251,.238,-.034),(.48,.266,.260,-.039),(.57,.266,.253,-.037),(.67,.253,.244,-.040),(.77,.223,.214,-.040),(.84,.155,.16,-.041),(.89,.01,.012,-.04)]
def dimensions(y):
    for k,(a,b) in enumerate(zip(PROFILE,PROFILE[1:])):
        if a[0]<=y<=b[0]:
            t=(y-a[0])/(b[0]-a[0])
            before=PROFILE[max(0,k-1)]; after=PROFILE[min(len(PROFILE)-1,k+2)]
            span=b[0]-a[0]
            out=[]
            for i in range(1,4):
                ma=(b[i]-before[i])/(b[0]-before[0])*span
                mb=(after[i]-a[i])/(after[0]-a[0])*span
                out.append((2*t**3-3*t*t+1)*a[i]+(t**3-2*t*t+t)*ma+(-2*t**3+3*t*t)*b[i]+(t**3-t*t)*mb)
            return tuple(out)
    return PROFILE[0][1:] if y<PROFILE[0][0] else PROFILE[-1][1:]

def front(x,y):
    w,d,c=dimensions(y)
    z=c+d*math.sqrt(max(0,1-(x/w)**2))
    cheek=.016*math.exp(-((abs(x)-.17)/.06)**2-((y-.42)/.09)**2)
    return z+cheek

verts=[]; faces=[]; rows=90; cols=96
for j in range(rows+1):
    y=.1+.79*j/rows
    w,d,c=dimensions(y)
    for i in range(cols):
        th=2*math.pi*i/cols
        x=w*math.sin(th)
        z=c+d*math.cos(th)
        if math.cos(th)>0: z=front(x,y)
        verts.append((x,y,z))
for j in range(rows):
    for i in range(cols):
        a=j*cols+i; b=j*cols+(i+1)%cols
        faces.append((a,b,b+cols,a+cols))
head=mesh('LexFace',verts,faces,skin)
ellipsoid('Lex neck',(0,.05,-.03),(.114,.175,.114),skin)

# Ears and the small turquoise / silver drop earring visible in the photo.
for sign in (-1,1):
    ellipsoid('Lex ear '+str(sign),(sign*.273,.455,-.005),(.052,.09,.041),skin)
    ellipsoid('Lex ear fold '+str(sign),(sign*.292,.455,.018),(.025,.052,.010),earskin)
    tube('Lex ear rim '+str(sign),[(sign*.282,.518,.022),(sign*.309,.487,.025),(sign*.301,.411,.025),(sign*.279,.399,.028)],.006,skin)
tube('Lex earring hoop',[(.302+.018*math.cos(a),.372+.022*math.sin(a),.021) for a in [i*math.pi/12 for i in range(24)]],.0025,silver,True)
ellipsoid('Lex turquoise bead',(.302,.331,.022),(.016,.021,.016),teal)
for i in range(3):
    tube('Lex silver earring drop '+str(i),[(.301+(i-1)*.007,.306,.023),(.304+(i-1)*.008,.271,.024),(.312+(i-1)*.007,.275,.024)],.0026,silver)

# Eyes are separate meshes named eye* as required for mouse-following.
for sign in (-1,1):
    x=sign*.105; y=.552; z=front(x,y)-.003
    eye=ellipsoid('eye_Lex_'+str(sign),(x,y,z),(.058,.026,.025),white)
    for name,offset,radii,mat in [('iris',.023,(.018,.020,.005),iris),('pupil',.028,(.008,.010,.003),pupil),('glint',.031,(.0035,.0035,.0015),white)]:
        part=ellipsoid('Lex '+name+' '+str(sign),(x-(.006 if name=='glint' else 0),y+(.008 if name=='glint' else 0),z+offset),radii,mat)
        world=part.matrix_world.copy(); part.parent=eye; part.matrix_world=world
    tube('Lex upper eyelid '+str(sign),[(x-.055,y,.212),(x-.027,y+.024,z+.014),(x+.018,y+.025,z+.017),(x+.056,y+.003,.211)],.005,skin)
    tube('Lex lower eyelid '+str(sign),[(x-.055,y-.002,.211),(x,y-.022,z+.012),(x+.056,y+.003,.211)],.0035,skin)
    tube('Lex brow '+str(sign),[(x-.065,.624,front(x-.065,.624)+.011),(x-.025,.637,front(x-.025,.637)+.014),(x+.032,.631,front(x+.032,.631)+.012),(x+.061,.622,front(x+.061,.622)+.008)],.010,hairmats[0])

# A shaped bridge and nose tip, nostrils, a restrained asymmetric smile.
ellipsoid('Lex nose bridge',(0,.486,.242),(.021,.077,.035),skin)
ellipsoid('Lex nose tip',(0,.408,.282),(.038,.028,.032),skin)
for s in (-1,1):
    ellipsoid('Lex nose wing '+str(s),(s*.033,.399,.260),(.017,.016,.018),skin)
    ellipsoid('Lex nostril '+str(s),(s*.030,.389,.278),(.012,.006,.005),earskin)

def mouth_y(x): return .278+.014*(x/.085)**2+.008*x/.085
mouthpts=[(x,mouth_y(x),front(x,mouth_y(x))+.006) for x in [(-.085+.17*i/16) for i in range(17)]]
tube('Lex smile opening',mouthpts,.0045,mouthmat)
tube('Lex upper lip',[(x,mouth_y(x)+.007+(.002 if abs(x)>.014 else 0),z+.003) for x,y,z in mouthpts],.004,lip)
tube('Lex lower lip',[(x,mouth_y(x)-.007*(1-(x/.085)**2),z+.004) for x,y,z in mouthpts],.005,lip)
tube('Lex teeth hint',[(x,mouth_y(x)+.002,front(x,mouth_y(x))+.009) for x in [-.043,-.024,0,.024,.043]],.0038,teeth)

# Swept black hair with a visible part and tapered, individually modeled locks.
hv=[]; hf=[]; hc=96; hr=32
for j in range(hr+1):
    t=j/hr
    for i in range(hc):
        a=2*math.pi*i/hc
        low=.59+.15*max(0,math.cos(a))-.10*max(0,-math.cos(a))
        low+=.022*math.sin(a*2)
        y=low+(.98-low)*math.sin(t*math.pi/2)
        radius=math.sqrt(max(.0001,1-((y-.55)/.44)**2))
        x=.292*radius*math.sin(a)
        z=-.043+.279*radius*math.cos(a)
        hv.append((x,y,z))
for j in range(hr):
    for i in range(hc):
        a=j*hc+i; b=j*hc+(i+1)%hc
        hf.append((a,b,b+hc,a+hc))
mesh('Lex parted hair cap',hv,hf,hairmats[0])

def hair_lock(name,points,width,mat):
    # Variable-radius swept mesh following a Catmull-Rom-like Bezier spline.
    curve=bpy.data.curves.new(name,'CURVE'); curve.dimensions='3D'; curve.resolution_u=10
    curve.bevel_depth=width; curve.bevel_resolution=3
    sp=curve.splines.new('BEZIER'); sp.bezier_points.add(len(points)-1)
    for i,(b,p) in enumerate(zip(sp.bezier_points,points)):
        b.co=xyz(p); b.handle_left_type=b.handle_right_type='AUTO'
        b.radius=.23 if i==len(points)-1 else (.65 if i==0 else 1)
    ob=bpy.data.objects.new(name,curve); scene.collection.objects.link(ob); curve.materials.append(mat)
    bpy.context.view_layer.objects.active=ob; ob.select_set(True); bpy.ops.object.convert(target='MESH'); ob.select_set(False)

for i in range(15):
    u=i/14
    points=[(.035+.028*u,.865+.03*u,.183-.18*u),(-.07-.09*u,.934-.025*u,.172-.16*u),(-.19-.033*u,.845-.03*u,.211-.16*u),(-.264+.037*u,.661-.063*u,.082-.08*u)]
    hair_lock('Lex left swept lock '+str(i),points,.012+.009*math.sin(u*math.pi),hairmats[i%4])
for i in range(17):
    u=i/16
    points=[(.049+.025*u,.868+.04*u,.181-.19*u),(.147+.034*u,.917-.026*u,.16-.17*u),(.248+.019*u,.815-.05*u,.131-.1*u),(.258-.044*u,.641-.07*u,.119-.06*u)]
    hair_lock('Lex right swept lock '+str(i),points,.014+.010*math.sin(u*math.pi),hairmats[i%3])
hair_lock('Lex front fringe',[(.055,.86,.21),(.135,.808,.232),(.16,.731,.215),(.127,.654,.222)],.027,hairmats[1])
hair_lock('Lex fine fringe',[(.081,.864,.208),(.167,.81,.216),(.185,.721,.185),(.166,.665,.176)],.017,hairmats[0])

# Rounded rectangular thin metal glasses; slightly transparent clear lenses.
def frame_points(cx,cy,w,h):
    pts=[]; r=.017
    for px,py,start in [(cx+w/2-r,cy+h/2-r,0),(cx-w/2+r,cy+h/2-r,90),(cx-w/2+r,cy-h/2+r,180),(cx+w/2-r,cy-h/2+r,270)]:
        for i in range(7):
            a=math.radians(start+i*90/6)
            x=px+r*math.cos(a); y=py+r*math.sin(a)
            pts.append((x,y,.273-.042*abs(x)/.2))
    return pts
for s in (-1,1):
    pts=frame_points(s*.111,.55,.170,.089)
    tube('Lex glasses rim '+str(s),pts,.0030,silver,True)
    center=(s*.111,.55,.271-.042*.111/.2)
    mesh('Lex glasses lens '+str(s),[center]+pts,[(0,i+1,(i+1)%len(pts)+1) for i in range(len(pts))],glass)
    tube('Lex glasses temple '+str(s),[(s*.198,.568,.230),(s*.27,.565,.064),(s*.283,.493,-.024)],.0032,silver)
tube('Lex glasses bridge',[(-.028,.565,.27),(0,.574,.289),(.028,.565,.27)],.0031,silver)

# Softly modeled shirt, sleeves, pointed collar, seam and dark tie.
bodyrows=[(.056,.112,.094,-.055),(-.025,.31,.16,-.05),(-.095,.49,.198,-.048),(-.24,.51,.23,-.045),(-.55,.455,.24,-.042),(-.86,.414,.205,-.044),(-1.02,.393,.155,-.051)]
bv=[]; bf=[]; count=64
for y,w,d,c in bodyrows:
    for i in range(count):
        a=i/count*2*math.pi; bv.append((w*math.sin(a),y,c+d*math.cos(a)))
for j in range(len(bodyrows)-1):
    for i in range(count):
        a=j*count+i; b=j*count+(i+1)%count
        bf.append((a,a+count,b+count,b))
body=mesh('Lex shirt torso',bv,bf,shirt)
sub=body.modifiers.new('Smooth shirt','SUBSURF'); sub.levels=2
for s in (-1,1):
    sleeve=ellipsoid('Lex shirt sleeve '+str(s),(s*.434,-.597,-.05),(.159,.433,.174),shirt,40,30)
    sleeve.rotation_euler[1]=s*.09
    tube('Lex shoulder seam '+str(s),[(s*.30,-.056,.049),(s*.404,-.135,.060),(s*.475,-.28,.076)],.0021,seam)
    tube('Lex sleeve crease '+str(s),[(s*.49,-.36,.117),(s*.49,-.45,.129),(s*.50,-.59,.115)],.0016,seam)
for s in (-1,1):
    v=[(s*.065,.065,.109),(s*.176,-.006,.164),(s*.19,-.164,.226),(s*.056,-.066,.222)]
    co=mesh('Lex pointed collar '+str(s),v,[(0,1,2,3)],collar)
    solid=co.modifiers.new('Collar thickness','SOLIDIFY'); solid.thickness=.007
    bevel=co.modifiers.new('Collar edge','BEVEL'); bevel.width=.006; bevel.segments=3
    tube('Lex collar stitching '+str(s),[(s*.075,.052,.116),(s*.164,-.011,.176),(s*.178,-.143,.236)],.0015,seam)
tube('Lex shirt placket',[(0,-.16,.23),(0,-.39,.209),(0,-.68,.19),(0,-.96,.117)],.003,collar)
for y in [-.25,-.42,-.59,-.77]:
    ellipsoid('Lex shirt button '+str(y),(0,y,.227 if y>-.5 else .195),(.009,.009,.005),collar,16,10)
ellipsoid('Lex tie knot',(0,-.105,.242),(.030,.034,.019),tie)
mesh('Lex tie blade',[(-.025,-.125,.264),(.025,-.125,.264),(.049,-.62,.213),(0,-.695,.201),(-.049,-.62,.213)],[(0,1,2,3,4)],tie)

# Shared transparent atlas. Each face patch uses a different randomly selected
# grid cell, conformed to the actual face equation with small surface offset.
image=bpy.data.images.load(str(ATLAS)); image.pack(); image.filepath='//lex-stickers.png'
stickermat=bpy.data.materials.new('Lex randomized stickers'); stickermat.use_nodes=True
nodes=stickermat.node_tree.nodes; links=stickermat.node_tree.links
bsdf=nodes.get('Principled BSDF'); tex=nodes.new('ShaderNodeTexImage'); tex.image=image
links.new(tex.outputs['Color'],bsdf.inputs['Base Color']); links.new(tex.outputs['Alpha'],bsdf.inputs['Alpha'])
bsdf.inputs['Roughness'].default_value=.52
stickermat.surface_render_method='DITHERED'
cells=rng.sample(range(16),10)
positions=[]
for region in [(-.178,-.112,.34,.47,3),(.114,.181,.34,.46,3),(-.14,.11,.676,.72,2),(-.17,-.12,.245,.30,1),(.12,.17,.25,.31,1)]:
    xmin,xmax,ymin,ymax,count=region
    for _ in range(count):
        for attempt in range(60):
            x=rng.uniform(xmin,xmax); y=rng.uniform(ymin,ymax)
            size=rng.uniform(.047,.067)
            if all(math.hypot(x-p['x'],y-p['y'])>(size+p['size'])*.43 for p in positions): break
        positions.append(dict(x=x,y=y,size=size,rotation=rng.uniform(-.5,.5)))
for index,(cell,p) in enumerate(zip(cells,positions)):
    v=[]; uv=[]; f=[]; res=10
    cr=math.cos(p['rotation']); sr=math.sin(p['rotation'])
    for j in range(res+1):
        for i in range(res+1):
            u=i/res; t=j/res; dx=(u-.5)*p['size']; dy=(t-.5)*p['size']
            x=p['x']+dx*cr-dy*sr; y=p['y']+dx*sr+dy*cr
            v.append((x,y,front(x,y)+.0028+index*.00005))
            uv.append(((cell%4+u)/4,(3-cell//4+t)/4))
    for j in range(res):
        for i in range(res):
            a=j*(res+1)+i; f.append((a,a+1,a+res+2,a+res+1))
    ob=mesh('decal_Lex_'+str(index).zfill(2),v,f,stickermat,uv)
    ob['atlas_cell']=cell; ob['random_seed']=SEED; ob['placement']=json.dumps(p)

# Retain the tutorial's five timeline anchors and 350-frame CameraAction.
scene.render.fps=24
scene.frame_set(0)
scene.render.engine='CYCLES'
scene.cycles.samples=48
scene.cycles.use_denoising=True
scene.render.resolution_x=1280; scene.render.resolution_y=720; scene.render.resolution_percentage=100
world=bpy.data.worlds.new('Lex studio world'); scene.world=world; world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.13,.16,.21,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.6
for name,pos,power,size,color in [('Key',(2,3,4),300,3,(1,.88,.79)),('Fill',(-2,1,3),220,3,(.73,.86,1)),('Rim',(1,2,-2),250,2,(.70,.83,1))]:
    light=bpy.data.lights.new('Lex studio '+name,'AREA'); light.energy=power; light.shape='DISK'; light.size=size; light.color=color
    ob=bpy.data.objects.new(light.name,light); scene.collection.objects.link(ob); ob.location=xyz(pos)
    ob.rotation_euler=(Vector(xyz((0,.4,0)))-ob.location).to_track_quat('-Z','Y').to_euler()
scene.view_settings.view_transform='AgX'
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ROOT/'deploy/lex-blender-preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'blender/lex.blend'))
bpy.ops.export_scene.gltf(filepath=str(ASSET/'lex.glb'),export_format='GLB',export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_cameras=True,export_lights=False,export_apply=True)

# Alpha mask prevents rectangular transparent decal shadows in WebGL.
glb=bytearray((ASSET/'lex.glb').read_bytes()); jsonlen=struct.unpack_from('<I',glb,12)[0]
document=json.loads(glb[20:20+jsonlen]); rest=glb[20+jsonlen:]
for m in document.get('materials',[]):
    if m.get('name')=='Lex randomized stickers':
        m['alphaMode']='MASK'; m['alphaCutoff']=.3; m['doubleSided']=True
encoded=json.dumps(document,separators=(',',':'),ensure_ascii=False).encode('utf-8')
encoded+=b' '*((-len(encoded))%4)
packed=struct.pack('<4sII','glTF'.encode(),2,20+len(encoded)+len(rest))+struct.pack('<I4s',len(encoded),b'JSON')+encoded+rest
(ASSET/'lex.glb').write_bytes(packed)
(ROOT/'blender/lex-sticker-layout.json').write_text(json.dumps({'seed':SEED,'atlas_cells':cells,'placements':positions},indent=2),encoding='utf-8')
print('LEX_GLB_SUMMARY',json.dumps({'nodes':len(document.get('nodes',[])),'meshes':len(document.get('meshes',[])),'animations':[a['name'] for a in document.get('animations',[])],'anchors':[n['name'] for n in document.get('nodes',[]) if n.get('name','').startswith('focus-')],'bytes':len(packed)}))
bpy.ops.render.render(write_still=True)
