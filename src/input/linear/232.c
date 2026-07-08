/*@ requires y > 2; */
void foo232(unsigned int y) {

    unsigned int x;

    x = 2;


    while (x < y) {
       if (x < y / x) {
       x *= x;
      }
       else {
       x++;
      }
      }

    /*@ assert x == y; */

  }