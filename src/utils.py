import jax.numpy as np
import meshio
import jax
import jax.numpy as np
import numpy as onp
import orix
import time
import matplotlib.pyplot as plt
from orix import plot, sampling
from orix.crystal_map import Phase
from orix.quaternion import Orientation, symmetry
from orix.vector import Vector3d
from src.arguments import args
from sklearn.decomposition import PCA


def unpack_state(state):
    zeta = state[...,  0:1]
    eta = state[..., 1:]
    return zeta, eta


def get_unique_ori_colors():
    print(f"Debug info: args.num_oris = {args.num_oris}")
    # unique_oris = R.random(args.num_oris, random_state=0).as_euler('zxz', degrees=True)
    ori2 = Orientation.random(args.num_oris)
    ipfkey = plot.IPFColorKeyTSL(symmetry.Oh)
    ori2.symmetry = symmetry.Oh
    rgb_z = ipfkey.orientation2color(ori2)
    # ori2.scatter("ipf", c=rgb_z, direction=ipfkey.direction)
    return rgb_z


# def orix_exp():
#     # We'll want our plots to look a bit larger than the default size
#     new_params = {
#         "figure.facecolor": "w",
#         "figure.figsize": (20, 7),
#         "lines.markersize": 10,
#         "font.size": 15,
#         "axes.grid": True,
#     }
#     plt.rcParams.update(new_params)
#     pg = symmetry.Oh
#     ori2 = Orientation.random(1000)
#     ipfkey = plot.IPFColorKeyTSL(pg)
#     ori2.symmetry = ipfkey.symmetry
#     rgb_z = ipfkey.orientation2color(ori2)
#     ori2.scatter("ipf", c=rgb_z, direction=ipfkey.direction)



def obj_to_vtu():
    filepath = f'data/neper/domain.obj'
    file = open(filepath, 'r')
    lines = file.readlines()
    points = []
    cells_inds = []

    for i, line in enumerate(lines):
        l = line.split()
        if l[0] == 'v':
            points.append([float(l[1]), float(l[2]), float(l[3])])
        if l[0] == 'g':
            cells_inds.append([])
        if l[0] == 'f':
            cells_inds[-1].append([int(pt_ind) - 1 for pt_ind in l[1:]])

    cells = [('polyhedron', cells_inds)]

    # cell_data = {'u': [onp.ones(len(cells_inds), dtype=onp.float32)]}
    # cell_data = {'u': [onp.random.rand(len(cells_inds), 3)]}
    # cell_data = {'u': [onp.hstack((onp.zeros((len(cells_inds), 2)), onp.ones((len(cells_inds), 1))))]}
    # mesh = meshio.Mesh(points, cells, cell_data=cell_data)

    mesh = meshio.Mesh(points, cells)
    return mesh


def vtk_convert_from_server():
    args.case = 'fd'
    def vtk_convert_from_server_helper(number):
        filepath = f'data/vtk/sols/{args.case}/u{number}.vtu'
        mesh = meshio.read(filepath)
        mesh.write(filepath)

    vtk_convert_from_server_helper(0)
    vtk_convert_from_server_helper(120)


def walltime(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        func(*args, **kwargs)
        end_time = time.time()
        time_elapsed = end_time - start_time
        print(f"Time elapsed {time_elapsed} on platform {jax.lib.xla_bridge.get_backend().platform}") 
        return time_elapsed
    return wrapper


def compute_stats():
    def compute_stats_helper():
        # edges = onp.load(f"data/numpy/{case}/edges.npy")
        # volumes = onp.load(f"data/numpy/{case}/vols.npy")
        # centroids = onp.load(f"data/numpy/{case}/centroids.npy")
        # cell_ori_inds = onp.load(f"data/numpy/{case}/cell_ori_inds_{tick}.npy")
        # melt = onp.load(f"data/numpy/{case}/melt_{tick}.npy")
        # num_nodes = len(volumes)


        edges = onp.load(f"data/numpy/fd/edges.npy")
        volumes = onp.load(f"data/numpy/fd/vols.npy")
        centroids = onp.load(f"data/numpy/fd/centroids.npy")

        if case == 'fd':
            cell_ori_inds =onp.load(f"data/numpy/{case}/cell_ori_inds_{tick}.npy")
            melt = onp.load(f"data/numpy/{case}/melt_{tick}.npy")           
        else:
            grain_oris_inds = onp.load(f"data/numpy/{case}/cell_ori_inds_{tick}.npy")
            grain_melt = onp.load(f"data/numpy/{case}/melt_{tick}.npy")
            cell_grain_inds = onp.load(f"data/numpy/fd/cell_grain_inds.npy")
            cell_ori_inds = onp.take(grain_oris_inds, cell_grain_inds - 1, axis=0)
            melt = onp.take(grain_melt, cell_grain_inds - 1, axis=0)


        num_nodes = len(volumes)
        edges_in_order = [[] for _ in range(num_nodes)]

        print(f"Re-ordering edges...")
        for edge in edges:
            node1 = edge[0]
            node2 = edge[1]
            edges_in_order[node1].append(node2)
            edges_in_order[node2].append(node1)

        print(f"BFS...")
        visited = onp.zeros(num_nodes)
        grains = [[] for _ in range(args.num_oris)]
        for i in range(len(visited)):
            if visited[i] == 0 and melt[i]:
                oris_index = cell_ori_inds[i]
                grains[oris_index].append([])
                queue = [i]
                visited[i] = 1
                while queue:
                    s = queue.pop(0) 
                    grains[oris_index][-1].append(s)
                    connected_nodes = edges_in_order[s]
                    for cn in connected_nodes:
                        if visited[cn] == 0 and cell_ori_inds[cn] == oris_index and melt[cn]:
                            queue.append(cn)
                            visited[cn] = 1

        def compute_aspect_ratios(grain):
            vol = onp.sum(onp.array([volumes[g] for g in grain]))
            if len(grain) < 3:
                return 1., vol

            directions = onp.array([centroids[g] for g in grain])
            weighted_directions = onp.array([volumes[g]*centroids[g] for g in grain])
            vols = onp.array([volumes[g] for g in grain])

            # weighted_directions = weighted_directions - onp.mean(weighted_directions, axis=0)[None, :]

            pca.fit(weighted_directions)

            components = pca.components_
            ev = pca.explained_variance_
            lengths = onp.sqrt(ev)

            aspect_ratio = 2*lengths[0]/(lengths[1] + lengths[2])

            # if aspect_ratio > 20:
            #     print(f"\npca.components_ = \n{pca.components_}")
            #     print(f"\npca.explained_variance_ = {pca.explained_variance_}")
            #     print(f"\nsum of ev = {onp.sum(pca.explained_variance_)}")
            #     print(f"\npca.explained_variance_ratio_ = {pca.explained_variance_ratio_}")

            #     print(f"\naspect_ratio = {aspect_ratio}")
            #     print(f"\nlen(grain) = {len(grain)}")
            #     print(f"\ndirections = \n{directions}")
            #     print(f"\nweighted_directions = \n{weighted_directions}")
            #     print(f"\nvols = {vols}") 
            #     exit()

            return aspect_ratio, vol

        pca = PCA(n_components=3)
        print(f"Compute vols...")
        grain_vols = []
        aspect_ratios = []
        for i in range(len(grains)):
            grains_oris = grains[i] 
            for j in range(len(grains_oris)):
                grain = grains_oris[j]
                # vol = 0.
                # for g in grain:
                #     vol += volumes[g]
                aspect_ratio, vol = compute_aspect_ratios(grain)
                aspect_ratios.append(aspect_ratio)
                grain_vols.append(vol)

        grain_vols = onp.array(grain_vols)
        aspect_ratios = onp.array(aspect_ratios)
        onp.save(f"data/numpy/{case}/post_vols_{tick}.npy", grain_vols)
        onp.save(f"data/numpy/{case}/post_aspect_ratios_{tick}.npy", aspect_ratios)


    # cases = ['gn', 'fd']
    # ticks = ['ini', 'fnl']

    cases = ['gn', 'fd']
    ticks = ['fnl']
    for case in cases:
        for tick in ticks:
            compute_stats_helper()

def hist_plot():
    # fd_vols_ini = onp.load(f"data/numpy/fd/post_vols_ini.npy")
    # gn_vols_ini = onp.load(f"data/numpy/gn/post_vols_ini.npy")
    fd_vols_fnl = onp.load(f"data/numpy/fd/post_vols_fnl.npy")
    gn_vols_fnl = onp.load(f"data/numpy/gn/post_vols_fnl.npy")


    fd_aspect_ratios_fnl = onp.load(f"data/numpy/fd/post_aspect_ratios_fnl.npy")
    gn_aspect_ratios_fnl = onp.load(f"data/numpy/gn/post_aspect_ratios_fnl.npy")


    fig = plt.figure()

    # print(onp.mean()
    # print(onp.mean(gn_vols_fnl[gn_vols_fnl > 1e-7]))


    # val = onp.min(gn_vols_fnl)
    val = 1e-7

    # print(fd_vols_fnl[fd_vols_fnl < val])
    # print(gn_vols_fnl[gn_vols_fnl < val])
    print(onp.mean(fd_vols_fnl[fd_vols_fnl > val]))
    print(onp.mean(gn_vols_fnl[gn_vols_fnl > val]))
    print(onp.sum(fd_vols_fnl > val))
    print(onp.sum(gn_vols_fnl > val))

    print("\naspect ratios")

    print(onp.mean(fd_aspect_ratios_fnl[fd_vols_fnl > val]))
    print(onp.mean(gn_aspect_ratios_fnl[gn_vols_fnl > val]))

    # exit()
 

    # colors = ['blue', 'red', 'orange', 'green']
    # labels = ['fd_ini', 'gn_ini', 'fd_fnl', 'gn_fnl']
    # plt.hist([fd_vols_ini, gn_vols_ini, fd_vols_fnl, gn_vols_fnl], color=colors, bins=bins, label=labels)

    colors = ['blue', 'red']
    labels = ['fd_fnl', 'gn_fnl']
    plt.hist([fd_vols_fnl[fd_vols_fnl > val], gn_vols_fnl[gn_vols_fnl > val]], color=colors, bins=onp.linspace(0., 1e-5, 6), label=labels)

    # plt.hist([fd_aspect_ratios_fnl[fd_vols_fnl > val], gn_aspect_ratios_fnl[gn_vols_fnl > val]], color=colors, bins=onp.linspace(1, 4, 13), label=labels)


    plt.legend()


if __name__ == "__main__":
    # vtk_convert_from_server()
    # get_unique_ori_colors()
    # compute_stats()
    hist_plot()
    plt.show()

