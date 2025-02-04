import networkx as nx
import logging

from strainy.clustering.community_detection import find_communities
from strainy.clustering.build_adj_matrix import *
from strainy.clustering.build_data import *


logger = logging.getLogger()


def split_cluster(cl,cluster, data,cons,clSNP, bam, edge, R, I,only_with_common_snip=True):
    #logging.debug("Split cluster: " + str(cluster)+ " "+ str(only_with_common_snip))
    child_clusters = []
    reads=sorted(set(cl.loc[cl['Cluster'] == cluster,'ReadName'].values))
    if cluster==unclustered_group_N or cluster==unclustered_group_N2  or only_with_common_snip==False: #NA cluster
        m = build_adj_matrix(cl[cl['Cluster'] == cluster], data, clSNP, I, bam, edge, R, only_with_common_snip=False)
    else:
        m=build_adj_matrix(cl[cl['Cluster'] == cluster], data, clSNP, I, bam,edge,R)
    m = remove_edges(m, 1)
    m.columns=range(0,len(cl[cl['Cluster'] == cluster]['ReadName']))
    m.index=range(0,len(cl[cl['Cluster'] == cluster]['ReadName']))

    m = change_w(m, R)
    G_sub = nx.from_pandas_adjacency(m)
    cl_exist = sorted(set(cl.loc[cl['Cluster'] != 'NA','Cluster'].values))+list(cons.keys())
    cluster_membership = find_communities(G_sub)
    clN=0
    uncl=0
    reads = cl[cl['Cluster'] == cluster]['ReadName'].values

    new_cl_id_na = cluster + split_id

    while new_cl_id_na in cl_exist:
        new_cl_id_na = new_cl_id_na + 1

    if len(set(cluster_membership.values()))>0:
        for value in set(cluster_membership.values()):
            group = [k for k, v in cluster_membership.items() if v == value]
            if len(group) > min_cluster_size:
                clN = clN + 1
                new_cl_id=new_cl_id_na+clN
                while new_cl_id in cl_exist:
                    new_cl_id=new_cl_id+1
                    child_clusters.append(new_cl_id)
                cl_exist.append(new_cl_id)
                for i in group:
                     mask = cl['ReadName'] == str(reads[i])
                     cl.loc[mask, "Cluster"] = new_cl_id
            else:
                uncl = uncl + 1
                for i in group:
                    mask = cl['ReadName'] == str(reads[i])
                if only_with_common_snip == True or cluster==1000000: #change it for parameter process NA or not
                    cl.loc[mask, "Cluster"] = new_cl_id_na
                    child_clusters.append(new_cl_id_na)
                else:
                    cl.loc[mask, "Cluster"] = 'NA'
    return ([new_cl_id_na, clN])


def build_adj_matrix_clusters (edge,cons,cl,flye_consensus, only_with_common_snip=True, set_slusters=None):
    if set_slusters==None:
        clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA','Cluster'].values))
    else:
        clusters=set_slusters
    try:
        clusters.remove(0)
    except:
        pass
    Y=[]
    X=[]
    Z=[]
    sort=[]
    for k,v in cons.items():
        X.append(k)
        Y.append(int(v["Start"]))
        Z.append(int(v["Stop"]))
        sort.append([k,int(v["Start"]),int(v["Stop"])])
    sorted_by_pos=[]

    for i in sorted(sort, key=lambda sort: [sort[2], sort[1]]):
        sorted_by_pos.append(i[0])
    clusters=sorted(set(sorted_by_pos) & set(clusters), key=sorted_by_pos.index)
    m = pd.DataFrame(-1, index=clusters, columns=clusters)

    for i in range(0, m.shape[1]):
        first_cl=m.index[i]
        for k in range(i + 1, m.shape[1]):
            second_cl=m.index[k]

            if m[second_cl][first_cl] == -1:
                m[second_cl][first_cl] = distance_clusters(edge, first_cl, second_cl, cons, cl,flye_consensus, only_with_common_snip)
    return m


def join_clusters(cons, cl, R, edge, consensus, only_with_common_snip=True,set_clusters=None, only_nested=False):
    if only_with_common_snip==False:
        if set_clusters==None:
            M = build_adj_matrix_clusters(edge,cons, cl,consensus, False)
        else:
            M=build_adj_matrix_clusters(edge, cons, cl, consensus, False,set_clusters)
    else:
        if set_clusters == None:
            M = build_adj_matrix_clusters(edge,cons, cl,consensus, True)
        else:
            M = build_adj_matrix_clusters(edge, cons, cl, consensus, True, set_clusters)

    M=change_w(M,R)
    G_vis = nx.from_pandas_adjacency(M, create_using=nx.DiGraph)
    G_vis.remove_edges_from(list(nx.selfloop_edges(G_vis)))
    to_remove = []
    G_vis_before = nx.nx_agraph.to_agraph(G_vis)
    G_vis_before.layout(prog="neato")
    G_vis_before.draw("%s/graphs/cluster_GV_graph_before_remove_%s.png" % (StRainyArgs.output, edge))
    path_remove=[]
    for node in G_vis.nodes():
        neighbors = nx.all_neighbors(G_vis, node)
        for neighbor in list(neighbors):
            for n_path in nx.algorithms.all_simple_paths(G_vis, node, neighbor, cutoff=5):
                if len(n_path) == 3:
                    path_remove.append(n_path)

    for n_path in path_remove:
        try:
            G_vis.remove_edge(n_path[0], n_path[2])
        except:
            continue

    lis = list(nx.topological_sort(nx.line_graph(G_vis)))
    first = []
    last = []

    for i in lis:
        first.append(i[0])
        last.append(i[1])

    for i in lis:
        if first.count(i[0]) > 1 or last.count(i[1]) > 1:
            to_remove.append(i)
    G_vis.remove_edges_from(ebunch=to_remove)
    G_vis = nx.nx_agraph.to_agraph(G_vis)
    G_vis.layout(prog="neato")
    G_vis.draw("%s/graphs/cluster_GV_graph_%s.png" % (StRainyArgs.output, edge))
    G = nx.from_pandas_adjacency(M)
    for n_path in path_remove:
        try:
            G.remove_edge(n_path[0], n_path[2])
        except :
            continue
    G.remove_edges_from(ebunch=to_remove)

    nested={}
    nodes = list(G.nodes())

    for node in nodes:
        try:
            neighbors = nx.all_neighbors(G, node)
            for neighbor in list(neighbors):
                if cons[node]["Start"] < cons[neighbor]["Start"] and cons[node]["Stop"] > cons[neighbor]["Stop"]:
                    try:
                        G.remove_edge(node, neighbor)
                        logger.debug("REMOVE NESTED" + str(neighbor))
                        if len(nx.all_neighbors(G, neighbor))==1:
                            try:
                                nested[neighbor]=nested[neighbor].append(node)
                            except:
                                nodes=[node]
                                nested[neighbor] =nodes
                    except:
                        continue
        except:
            continue

    groups = list(nx.connected_components(G))
    if only_nested==True:
        for k,v in nested.items():
            if len(v)==1:
                cl.loc[cl['Cluster'] == k, 'Cluster'] = v[0]

    else:
        for group in groups:
            if len(group) > 1:
                for i in range(0, len(group)):
                    cl.loc[cl['Cluster'] == list(group)[i], 'Cluster'] = int(list(group)[0])+10000000
    return cl

def split_all(cl, cluster, data, cons,bam, edge, R, I, SNP_pos,reference_seq):
    if cons[cluster]["Strange"] == 1:
        clSNP = cons[cluster]["clSNP"]
        res = split_cluster(cl, cluster, data,cons, clSNP, bam, edge, R, I)
        new_cl_id_na=res[0]
        clN =res[1]
        cluster_consensuns(cl, new_cl_id_na, SNP_pos, data, cons, edge, reference_seq)

        if clN!=0: #if clN==0 we dont need split NA cluster
            split_cluster(cl, new_cl_id_na, data, cons,cons[new_cl_id_na]["clSNP"], bam, edge, R, I, False)
        clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA', 'Cluster'].values))

        if clN==1: #STOP LOOP IF EXIST
            cluster_consensuns(cl, new_cl_id_na + clN, SNP_pos, data, cons, edge, reference_seq)

        for cluster in clusters:
            if cluster not in cons:
                cluster_consensuns(cl, cluster, SNP_pos, data, cons, edge, reference_seq)
                split_all(cl, cluster, data, cons,bam, edge, R, I, SNP_pos,reference_seq)


def split_all2(cl, cluster, data, cons,bam, edge, R, I, SNP_pos,reference_seq):
    #TODO merge with previous function
    if cons[cluster]["Strange2"] == 1:
        clSNP = cons[cluster]["clSNP2"]
        res = split_cluster(cl, cluster, data, cons,clSNP, bam, edge, R, I)
        new_cl_id_na=res[0]
        clN =res[1]
        cluster_consensuns(cl, new_cl_id_na, SNP_pos, data, cons, edge, reference_seq)

        if clN!=0: #if clN==0 we dont need split NA cluster
            split_cluster(cl, new_cl_id_na, data,cons, cons[new_cl_id_na]["clSNP2"], bam, edge, R, I, False)
        clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA', 'Cluster'].values))

        if clN==1: #STOP LOOP IF EXIST
            cluster_consensuns(cl, new_cl_id_na + clN, SNP_pos, data, cons, edge, reference_seq)


        for cluster in clusters:
            if cluster not in cons:
                cluster_consensuns(cl, cluster, SNP_pos, data, cons, edge, reference_seq)
                split_all(cl, cluster, data, cons,bam, edge, R, I, SNP_pos,reference_seq)


def postprocess(bam, cl, SNP_pos, data, edge, R, I, flye_consensus):
    reference_seq = read_fasta_seq(StRainyArgs.fa, edge)
    cons = build_data_cons(cl, SNP_pos, data, edge, reference_seq)
    cl.to_csv("%s/clusters/1.csv" % StRainyArgs.output)
    clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA','Cluster'].values))
    cl.loc[cl['Cluster'] == 1000000, 'Cluster'] = 'NA'
    clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA', 'Cluster'].values))
    prev_clusters=clusters
    for cluster in clusters:
        split_all(cl, cluster, data, cons,bam, edge, R, I, SNP_pos,reference_seq)
        clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA', 'Cluster'].values))
        new_clusters=list(set(clusters) - set(prev_clusters))
        prev_clusters=clusters
        cl=join_clusters(cons, cl, R, edge, flye_consensus, False,new_clusters)
        clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA', 'Cluster'].values))

        for cluster in clusters:
            if cluster not in cons:
                cluster_consensuns(cl, cluster, SNP_pos, data, cons, edge, reference_seq)

    cl.to_csv("%s/clusters/2.csv" % StRainyArgs.output)
    clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA', 'Cluster'].values))

    logging.info("Split stage2: Break regions of low heterozygosity")
    for cluster in clusters:
        split_all2(cl, cluster, data, cons,bam, edge, R, I, SNP_pos,reference_seq)
    cl.loc[cl['Cluster'] == 'NA', 'Cluster'] = 1000000
    cluster_consensuns(cl, 1000000, SNP_pos, data, cons, edge, reference_seq)
    clSNP = cons[1000000]["clSNP"]
    split_all(cl, 1000000, data, cons, bam, edge, R, I, SNP_pos, reference_seq)
    cl = cl[cl['Cluster'] != 'NA']
    cl = cl[cl['Cluster'] != 1000000]
    counts = cl['Cluster'].value_counts(dropna=False)
    cl = cl[~cl['Cluster'].isin(counts[counts < 6].index)]  # change for cov*01.
    clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA', 'Cluster'].values))
    for cluster in clusters:
        if cluster not in cons:
            cluster_consensuns(cl, cluster, SNP_pos, data, cons, edge, reference_seq)
    cl = join_clusters(cons, cl, R, edge, flye_consensus)
    clusters = sorted(set(cl.loc[cl['Cluster'] != 'NA', 'Cluster'].values))
    for cluster in clusters:
        if cluster not in cons:
            cluster_consensuns(cl, cluster, SNP_pos, data, cons, edge, reference_seq)
    cl=join_clusters(cons, cl, R, edge, flye_consensus, False)
    cl = join_clusters(cons, cl, R, edge, flye_consensus, False,only_nested=True)
    return cl
