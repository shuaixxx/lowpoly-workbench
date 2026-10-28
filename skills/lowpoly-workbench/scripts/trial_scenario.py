"""Independent Blender integration trial; never run this in the user's live scene."""
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh

sys.path.insert(0,str(Path(__file__).resolve().parent))
from scenario_runtime import load_backend, review_meshes, UPSTREAM_COMMIT
from blender_bridge import ensure_importance_channel, export_patch, audit_geometry
import mesh_cases


def make_high():
    vertices,faces=[],[]
    n=64
    for j in range(13):
        z=-1.5+j*.25
        radius=1+.12*math.cos(z*1.8)
        for i in range(n):
            a=2*math.pi*i/n
            vertices.append((radius*math.cos(a),radius*math.sin(a),z))
    for j in range(12):
        for i in range(n):
            k=(i+1)%n
            faces.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
    faces.extend([tuple(reversed(range(n))),tuple(12*n+i for i in range(n))])
    mesh=bpy.data.meshes.new('TrialHigh_Mesh');mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new('TrialHigh_Synthetic',mesh);bpy.context.scene.collection.objects.link(obj)
    return obj


def recalc(obj):
    bm=bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(obj.data)
    finally:bm.free()
    obj.data.update()


def main():
    if not bpy.app.background or bpy.data.filepath:
        raise RuntimeError('Run in background factory startup with no user file loaded')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario-root',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--skip-render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):raise FileExistsError('Choose a new empty trial directory')
    out.mkdir(parents=True,exist_ok=True)
    R,A,V=load_backend(args.scenario_root)
    for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
    high=make_high()
    objects=[]
    for name,count in [('Tube_08',8),('Tube_16',16)]:
        obj=R.setup_cage(high,name=name,mirror=False,subsurf=0)
        R.tube(obj,high,[(0,0,z) for z in (-1.15,-.575,0.,.575,1.15)],n=count,start_dir=(1,0,0))
        for modifier in list(obj.modifiers):obj.modifiers.remove(modifier)
        recalc(obj);objects.append(obj)

    transition=R.setup_cage(high,name='Transition_16_to_08',mirror=False,subsurf=0)
    rings=R.tube(transition,high,[(0,0,z) for z in (-1.15,-.575,0.)],n=16,start_dir=(1,0,0))
    small=R.add_ring(transition,R.ring(high,(0,0,.65),(0,0,1),n=8,start_dir=(1,0,0)))
    junction=R.bridge_reduce(transition,rings[-1],small,target=high)
    top=R.add_ring(transition,R.ring(high,(0,0,1.15),(0,0,1),n=8,start_dir=(1,0,0)))
    R.bridge(transition,small,top)
    for modifier in list(transition.modifiers):transition.modifiers.remove(modifier)
    recalc(transition);objects.append(transition)

    triangulated=objects[0].copy();triangulated.data=objects[0].data.copy();triangulated.name='Tube_08_Triangles'
    bpy.context.scene.collection.objects.link(triangulated)
    bm=bmesh.new()
    try:
        bm.from_mesh(triangulated.data)
        bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(triangulated.data)
    finally:bm.free()
    objects.append(triangulated)

    reports,records=[],[]
    database=out/'cases.sqlite3'
    for i,obj in enumerate(objects):
        ensure_importance_channel(obj)
        obj['lowpoly_case_status']='unreviewed'
        obj['lowpoly_trial']='scenario-compatibility-v0.1'
        obj['importance_author']='unassigned'
        obj.location.x=(i-1.5)*3.2
        bpy.context.view_layer.update()
        report=audit_geometry(obj)
        assert report['topology']['loose_vertices']==0,report
        assert report['topology']['nonmanifold_edges_excluding_boundaries']==0,report
        assert report['topology']['zero_area_faces']==0,report
        assert report['importance']['assigned']==0,report
        assert report['uv_layers']==0,report
        assert R.tri_count(obj)==report['evaluated']['triangles'],report
        record=export_patch(obj,out/'cases'/f'{obj.name}.json',case_id='trial-'+obj.name,
            provenance={'kind':'synthetic-integration-trial','provider':'Scenario','commit':UPSTREAM_COMMIT,
                        'functions':['setup_cage','tube'] if i<2 else ['ring','add_ring','bridge_reduce','bridge'] if i==2 else ['bmesh-triangulate-negative-control']})
        descriptor=mesh_cases.add_case(database,record)
        assert descriptor['boundary_loops']==2,descriptor
        if i<3:assert descriptor['all_quads'],descriptor
        reports.append(report);records.append(record)
    assert mesh_cases.search(database,records[0],quads=True)['results']==[], 'Unreviewed trial was silently accepted'
    retrieved=mesh_cases.search(database,records[0],quads=True,include_unreviewed=True)
    assert len(retrieved['results'])==3,retrieved
    locked=mesh_cases.search(database,records[0],quads=True,lock_boundary=True,include_unreviewed=True)
    assert [r['id'] for r in locked['results']]==['trial-Tube_08'],locked
    high.hide_render=True;high.hide_set(True)
    for ob in bpy.context.selected_objects:ob.select_set(False)
    objects[2].select_set(True);bpy.context.view_layer.objects.active=objects[2]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_distance=16
                area.spaces.active.region_3d.view_location=(0,0,0)
    bpy.context.scene['trial_description']='Scenario geometry integration; all cases await user review; importance groups intentionally empty'
    blend=out/'scenario_trial.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    # Reopen the delivered file and verify persistent mesh and weight-channel state.
    names=[obj.name for obj in objects]
    bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False)
    objects=[bpy.data.objects[name] for name in names]
    assert all(ob.vertex_groups.get('lp_importance') is not None for ob in objects)
    assert all(audit_geometry(ob)['importance']['assigned']==0 for ob in objects)
    render_paths=[]
    if not args.skip_render:
        for obj in objects[:3]:
            in_front=obj.show_in_front
            sheet=review_meshes(V,[obj],out/'views'/obj.name,views=('front','threequarter'),modes=('matcap','wire'),res=320)
            assert obj.show_in_front==in_front, 'Review changed caller display state'
            render_paths.append(str(sheet))
    result={'status':'passed','prototype_version':'0.1.1','blender_version':bpy.app.version_string,
            'scenario_commit':UPSTREAM_COMMIT,'tested_functions':['setup_cage','ring','tube','add_ring','bridge','bridge_reduce','tri_count','bx_review.review'],
            'compatibility_adjustments':['temporarily_clear_show_in_front_for_workbench_wire_review_and_restore'],
            'junction':junction,'objects':reports,'retrieval':retrieved,'locked_boundary_retrieval':locked,
            'blend_reopened':True,'blend':str(blend),'database':str(database),'review_sheets':render_paths,
            'user_asset_modified':False,'weights_painted':False,'bake_verified':False,'user_acceptance':'pending'}
    (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESULT '+json.dumps({'status':result['status'],'blend':str(blend),'objects':len(objects),'candidate_count':len(retrieved['results']),'report':str(out/'report.json')},ensure_ascii=False))


if __name__=='__main__':main()
