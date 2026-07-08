/*@ requires n <= 20000001; */
void foo306(unsigned int n) {
    unsigned int j;
    unsigned int i;
    unsigned int l;

    i = 0;
    j = 0;
    l = 0;


    while (l < n) {
       if ((l % 2) == 0) {
       i = i + 1;
      }
       else{
       j = j + 1;
      }
       l = l + 1;
      }

    /*@ assert (i + j); */

  }