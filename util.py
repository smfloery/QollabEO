from datetime import datetime

def create_quarter_strings():
    
    time_ivals = []
    
    for i in range(24):
        for j in ["00", "15", "30", "45"]:
            time_ivals.append("%02d:%s" % (i,j))
    
    return time_ivals
            
def get_current_from_to():
    now = datetime.now()
    current_hour = int(now.strftime("%H"))
    time_from = current_hour + 1
    if time_from == 24:
        time_from = 0
    time_to = current_hour + 2
    if time_to == 24:
        time_to = 0
    from_str = "%02d:00" % (time_from)
    to_str = "%02d:00" % (time_to)
    
    return from_str, to_str