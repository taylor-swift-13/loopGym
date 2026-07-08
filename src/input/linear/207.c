int unknown();
/*@ requires y <= 1000000; */
void foo207(int y) {

    int x;


        x = unknown();

    while(x < 100 && y > 0){
       x = x + y;
      }

    /*@ assert (y <= 0 || (y > 0 && x >= 100) ==> (y <= 0 || (x >= 100 && y > 0))); */

  }