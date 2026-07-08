int unknown();
/*@ requires x != y; */
void foo271(int x, int y) {

    int t;

    t = unknown();
    y = t;


    
    while (unknown()) {
       if(x > 0)
       y = y + x;
      }

    /*@ assert y >= t; */

  }