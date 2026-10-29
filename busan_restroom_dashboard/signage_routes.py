"""Map-space walkable polylines, clear of facility rectangles and ticket counter."""
import json

# Start outside room 1's ring; approach each destination without crossing fixtures.
ROUTES={
    'north':{
        'south':[(192,500),(260,500),(260,435),(880,435),(914,440)],
        'east':[(192,500),(260,500),(260,435),(440,435),(440,240),(600,240),(600,226)],
    }
}


def route_path(current,destination):
    points=ROUTES.get(current,{}).get(destination,[])
    return ' '.join(('M' if index==0 else 'L')+f'{x} {y}' for index,(x,y) in enumerate(points))


def script():
    return 'const signageRoutes='+json.dumps(ROUTES)+';\nfunction signageRoutePath(current,destination){const points=signageRoutes[current]?.[destination]||[];return points.map(([x,y],i)=>(i?"L":"M")+x+" "+y).join(" ");}\n'
