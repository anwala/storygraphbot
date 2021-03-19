#!/usr/bin/env python3
import sys
import os
import os.path
import json
from datetime import datetime
import argparse



def get_data():
	cmd = (f'sgtk --pretty-print -o graphs_tmp/current_storygraphdata.json maxgraph --cluster-stories-by="max_avg_degree" --cluster-stories --start-datetime="{args.start_datetime}" --end-datetime="{args.end_datetime}" > graphs_tmp/console_output.log  2>&1')
	a = os.system(cmd)
	read_file = open("graphs_tmp/current_storygraphdata.json", "r")
	data = json.load(read_file)
	return(data)


def get_cache(date):
	cache_filename = "cache/"+'cache_'+date
	if os.path.isfile(cache_filename):
		cache = json.load(open(cache_filename, "r"))
		#print("cache exists")
	else:
		cache = new_cache(date)
		#print("New cache initiated")
	return(cache)


def new_cache(date):
	#current_date = datetime.today().strftime('%Y-%m-%d')
	current_date = date
	#current_datetime = datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
	cache = {
			current_date: {  
				"start_datetime": current_date+' 00:00:00',
				"end_datetime": "",
				"stories": [
					]
				}
			}
	return(cache)



def overlap_stories(first, second):
	#first, second = set(first), set(second) 
	intersection = float(len(first & second))
	minimum = min(len(first), len(second))
	if( minimum != 0 ):
		return(round(intersection/minimum, 4))
	else:
		return(0) 


def get_stories_uri_datetimes(jdata): 
	#extract graph_uri_local_datetime from data(list of list) 
	stories_uri_datetimes = []
	for story in jdata[date]["stories"]:
		story_uri_datetimes = set([graph["graph_uri_local_datetime"] for graph in story["graph_ids"]])
		stories_uri_datetimes.append(story_uri_datetimes)
	return(stories_uri_datetimes)



def map_cache_stories(cache, data):
	map_cachestories = {} 	
	topstory_incache = True

	stories_uri_dts =  get_stories_uri_datetimes(data["story_clusters"])
	cachedstories_uri_dts = get_stories_uri_datetimes(cache)

	if cachedstories_uri_dts == []	:
		#print("Empty cache")
		topstory_incache = False
	else:
		for sn in range(len(stories_uri_dts)):
			s_uridt = stories_uri_dts[sn]
			coeff_list = [overlap_stories(cs_uridt, s_uridt) for cs_uridt in cachedstories_uri_dts]
			maxcoeff = max(coeff_list) 

			if maxcoeff >= args.overlap_threshold:
				c_indx = coeff_list.index(maxcoeff)
				story_id = cache_stories[c_indx]["story_id"]
				new_graphs = s_uridt - cachedstories_uri_dts[c_indx]
				update = {"sgtkdata_story": sn, "new_graphs": list(new_graphs)}
				#map_cachestories.update({c_indx: [sn, supdate]})

				map_cachestories.update({story_id: update})

			elif sn == 0:
				topstory_incache = False
				#print("Top story is not in cache")
	
			if len(map_cachestories) == len(cachedstories_uri_dts):
				break
	#mapperfile
	mapper_update(map_cachestories)
	return(map_cachestories, topstory_incache)



def mapper_update(map_cachestories):
	''' mapping json shows the update on the tracked stories at each timestamp'''
	mapper_file = "mapper_"+ date
	if os.path.isfile(mapper_file):
		try:
			mapper = json.load(open(mapper_file, "r"))
		except Exception as e:
			print(f"Error: Please clear the {mapper_file} created in earlier test run. cmd: rm -f {mapper_file}")
			sys.exit()
	else:
		mapper = {}

	mapper[data["end_date"]] = map_cachestories		
	json.dump(mapper, open(mapper_file, 'w'))




def get_topstory(stories):
	top_story = stories[0]		
	#check activation degree
	c = top_story["max_avg_degree"] > args.activation_degree
	if c:
		return(top_story)
	#else:
		#print("No top story")



def new_story(top_story, cache_stories):
	#print("Creating 1 new thread for new top story")			
	story_id = f'{date.replace("-","")}_{len(cache_stories)}'
	top_story["story_id"] = story_id
	top_story["reported_graphs"] = []
	story_graph = top_story["graph_ids"][0]
	#post story to file
	post_story(story_id, story_graph)	
	#update cache
	top_story["reported_graphs"].append(story_graph)
	cache_stories.append(top_story) 	
	return(story_id, story_graph)



def get_story_cache(story_id):
	for indx in range(len(cache_stories)):
		story = cache_stories[indx]
		if story["story_id"] == story_id:
			return(story, indx)



def update_story(story_id, update):
	story_cache, c_indx = get_story_cache(story_id)
	data_sidx = update["sgtkdata_story"]
	new_graphs = update['new_graphs']

	if new_graphs:
		story_data = stories[data_sidx] 			
		story_graphs = story_data["graph_ids"]

		if story_graphs[0]['id'] != story_cache["graph_ids"][0]['id']:
			latest_graph = story_graphs[0]
		else: 
			#top snapshot hasnt changed
			latest_graph_uri = sorted(new_graphs, reverse=True)[0]
			latest_story_graphs = [dic for dic in story_graphs if dic["graph_uri_local_datetime"]==latest_graph_uri] 
			l_id = sorted(latest_story_graphs, key=lambda k: int(k['id'].split("-")[1]), reverse=True) #id used identify graphs
			latest_graph = l_id[0]
		
		post_story(story_id, latest_graph)	
		#update_cache
		story_data["story_id"] = story_id	
		story_data["reported_graphs"] = story_cache["reported_graphs"]												
		story_data["reported_graphs"].append(latest_graph)													
		cache_stories[c_indx] = story_data 				
		return(True)	



def post_story(story_id, story_graph):
	'''Post story to file'''
	story_fname = "output/story_"+str(story_id)+".txt"
	if os.path.exists(story_fname):
		mode = 'a+' 
	else:
		mode = 'w+'
	story_file = open(story_fname, mode)

	#format graph
	formatted_graph = pretty_print_graph(story_id, story_graph)	

	#print story to file		
	for k,v in formatted_graph.items(): 
		story_file.write("{}:{}\n".format(k,v))			
	story_file.write("\n")



def pretty_print_graph(story_id, story_graph):
	#format graph
	formatted_graph = {
		"Story ID" : story_id,
		"Title" : story_graph['max_node_title'],		
		"Avg Degree" : story_graph['avg_degree'],
		"Graph URI": story_graph['graph_uri']
			}	
	return(formatted_graph)



def get_generic_args():
    parser = argparse.ArgumentParser(formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30), description='Query StoryGraphbot')
    parser.add_argument('--start-datetime', default='', help='"YYYY-mm-DD HH:MM:SS" datetime for filtering graphs based on datetime')
    parser.add_argument('--end-datetime', default='', help='"YYYY-mm-DD HH:MM:SS" datetime for filtering graphs based on datetime')    
    parser.add_argument('-a','--activation-degree', dest='activation_degree', default= 5.0, type=float, help='The criteria for filtering top stories of the day')
    parser.add_argument('-ol','--overlap-threshold', default=0.9, type=float, help='The criteria for matching two stories')
    return parser




if __name__ == "__main__":
	args = get_generic_args().parse_args()
	data = get_data()
	date = list(data["story_clusters"])[0] 
	cache = get_cache(date)
	cache_stories = cache[date]['stories']

	map_cachestories, st0_incache = map_cache_stories(cache, data)
	#print(map_cachestories)
	stories = data["story_clusters"][date]["stories"]	

	if stories == []:
		sys.exit("No stories in the new data")

	top_story = get_topstory(stories)

	print("Activation degree: "+str(args.activation_degree))
	print("Overlap threshold: "+str(args.overlap_threshold))

	new_story_id = None
	if top_story:		
		if not st0_incache or not map_cachestories: 			#add story to cache
			new_story_id, new_story = new_story(top_story, cache_stories)
	print(f'New top story id: {new_story_id}')


	updated_ids = []
	if map_cachestories:   	
		for story_id, update in map_cachestories.items():
			is_updated = update_story(story_id, update)
			if is_updated:
				updated_ids.append(story_id)	

	if updated_ids == []:
		updated_ids = None
	else:
		updated_ids = ', '.join(updated_ids)
	print(f'Updates of previous stories: {updated_ids}')
 							

	#dump_cache 
	cache[date]["end_datetime"] = data["end_date"]
	json.dump(cache, open('cache/cache_'+date, 'w'))	


	#print stories on console
	print("\nAll Stories:\n")
	for story in cache_stories:	
		story_id = story["story_id"]
		reported_graphs = story["reported_graphs"]

		formatted_story = pretty_print_graph(story_id, reported_graphs[-1])
		for k,v in formatted_story.items(): 
			print(f'\t{k}: {v}')

		if len(reported_graphs) > 1:	
			print(f'\t\tHistory:')
			for graph in reported_graphs[:-1]:
				formatted_story = pretty_print_graph(story_id, graph)
				for k,v in formatted_story.items():
					if k!="Story ID": 
						print(f'\t\t\t{k}: {v}')			
		print('')


	#if len(map_cachestories) < len(cache_stories):
	#print("\nThere are no updates on the other stories")

