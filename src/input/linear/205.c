int unknown();
void foo205() {

    int x;
    int y;

    x = unknown();
    y = x;


    
    while(x < 1024){
       x = x + 1;
       y = y + 1;
      }

    /*@ assert x == y; */

  }