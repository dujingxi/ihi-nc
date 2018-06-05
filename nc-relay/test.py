import copy

dd = {"421": ["421", "321", "516", "229"], "517":["517", "516", "229"], "33": ["33", "516", "229"], "324": ["324", "774", "771"], "772": ["772", "771"], "99":["99", "87", "220"]}

def tt(d):
    dd = copy.copy(d)
    res_d = {}; res_l = []
    while len(dd)>0:
        k_v = dd.popitem()
        last_v = k_v[1][-1]
        if last_v not in res_d:
            res_d[last_v] = [k_v[0]]
        else:
            res_d[last_v].append(k_v[0])
    result = {}
    for same_net in res_d.values():        # [['772', '324'], ['33', '421', '517'], ['99']]
        count = len(same_net)
        for level in d[same_net[0]]:
            n = 0
            for i in range(count):
                if level in d[same_net[i]]: n+=1
            if n == count:
                result[level] = same_net
                break
    return result

print tt(dd)
