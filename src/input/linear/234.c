void foo234(unsigned int N) {

    unsigned int x;

    x = 0;


    while (x < N) {
       x += 2;
      }

    /*@ assert x % 2 == 0; */

  }