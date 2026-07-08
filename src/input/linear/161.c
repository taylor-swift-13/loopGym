int unknown();
void foo161() {

    int x;
    int y;
    int i;
    int j;

    i = unknown();    j = unknown();
    x = i;
    y = j;


    
    while(x != 0){
       x = x - 1;
       y = y - 1;
      }

    /*@ assert (y != 0) ==> (i != j); */

  }